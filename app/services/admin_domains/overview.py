import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import ItemKind
from app.models.canonical import (
    AdminAuditLog,
    BundleReleaseProviderLink,
    CharacterAppearance,
    Edition,
    EntityOrganization,
    EntityPerson,
    ExternalProviderId,
    ImageAsset,
    ImageCacheEntry,
    Item,
    ItemProviderLink,
    MetadataProposal,
    ProviderIngestJob,
    Series,
    SeriesProviderLink,
    StoryArcItem,
    Variant,
    VolumeProviderLink,
    Volume,
)
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminCatalogSummaryResponse,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    ProviderCacheStatsResponse,
    ProviderCacheSummaryResponse,
    ProviderIngestHistoryEntry,
    ProviderStatusResponse,
)
from app.search.client import SearchClient
from app.search.documents import item_search_document


_SEARCH_HISTORY: deque[AdminSearchHistoryEntry] = deque(maxlen=20)
logger = logging.getLogger(__name__)


def _meili_document_count(stats: Any) -> int | None:
    if isinstance(stats, dict):
        value = stats.get("numberOfDocuments")
        if value is None:
            value = stats.get("number_of_documents")
    else:
        value = getattr(stats, "number_of_documents", None)
        if value is None:
            value = getattr(stats, "numberOfDocuments", None)
        if value is None and hasattr(stats, "model_dump"):
            dumped = stats.model_dump(by_alias=True)
            value = dumped.get("numberOfDocuments")
            if value is None:
                value = dumped.get("number_of_documents")
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            return None
    return value if isinstance(value, int) else None


class AdminOverviewService:
    def __init__(
        self,
        *,
        db: AsyncSession,
        providers: Any,
        search_client_cls: type[SearchClient] | None = None,
        provider_search_state: Any,
        provider_preview_state: Any,
        duplicate_group_count: Callable[[], Awaitable[int]],
        ingest_history_reader: Callable[[], list[ProviderIngestHistoryEntry]],
    ) -> None:
        self.db = db
        self.providers = providers
        self.search_client_cls = search_client_cls or SearchClient
        self.provider_search_state = provider_search_state
        self.provider_preview_state = provider_preview_state
        self._duplicate_group_count = duplicate_group_count
        self._ingest_history_reader = ingest_history_reader

    async def provider_statuses(self) -> list[ProviderStatusResponse]:
        return [
            ProviderStatusResponse(
                name=status.name,
                display_name=status.display_name,
                kind=status.kind.value,
                supported_kinds=[kind.value for kind in status.supported_kinds],
                status="live" if status.is_configured else "stub",
                is_configured=status.is_configured,
                supports_search=status.supports_search,
                supports_ingest=status.supports_ingest,
                requires_user_key=status.requires_user_key,
                non_commercial_only=status.non_commercial_only,
                allows_redistribution=status.allows_redistribution,
                allows_image_mirroring=status.allows_image_mirroring,
                requires_attribution=status.requires_attribution,
                license_name=status.license_name,
                terms_url=status.terms_url,
                attribution_url=status.attribution_url,
                rate_limit=status.rate_limit,
                cache_policy=status.cache_policy,
                message=status.status_message,
            )
            for status in self.providers.status_entries()
        ]

    async def provider_cache_stats(self) -> ProviderCacheSummaryResponse:
        return ProviderCacheSummaryResponse(
            search=ProviderCacheStatsResponse(**(await self.provider_search_state.stats())),
            preview=ProviderCacheStatsResponse(**(await self.provider_preview_state.stats())),
        )

    async def catalog_summary(self) -> AdminCatalogSummaryResponse:
        duplicate_groups = await self._duplicate_group_count()
        return AdminCatalogSummaryResponse(
            items=await self._count(Item),
            items_by_kind=await self._item_counts_by_kind(),
            series=await self._count(Series),
            volumes=await self._count(Volume),
            editions=await self._count(Edition),
            variants=await self._count(Variant),
            provider_links=await self._provider_link_count(),
            image_assets=await self._count_image_assets(),
            image_cache_entries=await self._count(ImageCacheEntry),
            pending_proposals=await self._count_pending_proposals(),
            missing_cover_items=await self._count_missing_cover_items(),
            missing_provider_link_items=await self._count_missing_provider_link_items(),
            duplicate_candidate_groups=duplicate_groups,
            provider_ingest_successes=await self._provider_ingest_success_count(),
            provider_ingest_failures=await self._provider_ingest_failure_count(),
        )

    async def search_status(self) -> AdminSearchStatusResponse:
        try:
            client = self.search_client_cls()
            client.client.health()
            stats = client.client.index(client.index_name).get_stats()
            document_count = _meili_document_count(stats)
        except Exception as exc:
            logger.warning("admin_search_status_failed error=%s", exc)
            return AdminSearchStatusResponse(
                ok=False,
                index_name=self.search_client_cls.index_name,
                error=str(exc),
            )
        return AdminSearchStatusResponse(
            ok=True,
            index_name=client.index_name,
            document_count=document_count,
            is_empty=document_count == 0 if document_count is not None else None,
        )

    async def reindex_search(self) -> AdminSearchReindexResponse:
        search = self.search_client_cls()
        try:
            await search.configure()
            documents = await self._search_documents()
            await search.replace_documents(documents)
        except Exception as exc:
            logger.warning("admin_search_reindex_failed index=%s error=%s", search.index_name, exc)
            response = AdminSearchReindexResponse(
                ok=False,
                index_name=search.index_name,
                indexed_documents=0,
                error=str(exc),
            )
            self._record_search_history(response)
            return response
        response = AdminSearchReindexResponse(
            ok=True,
            index_name=search.index_name,
            indexed_documents=len(documents),
        )
        self._record_search_history(response)
        return response

    def search_history(self) -> list[AdminSearchHistoryEntry]:
        return list(_SEARCH_HISTORY)

    async def audit_logs(
        self,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        limit: int = 25,
    ) -> list[AdminAuditLogResponse]:
        stmt = select(AdminAuditLog).order_by(
            AdminAuditLog.created_at.desc(),
            AdminAuditLog.id.desc(),
        )
        if action:
            stmt = stmt.where(AdminAuditLog.action == action)
        if entity_type:
            stmt = stmt.where(AdminAuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AdminAuditLog.entity_id == entity_id)
        result = await self.db.execute(stmt.limit(limit))
        return [AdminAuditLogResponse.model_validate(row) for row in result.scalars()]

    async def _count(self, model: type) -> int:
        return int(await self.db.scalar(select(func.count()).select_from(model)) or 0)

    async def _item_counts_by_kind(self) -> dict[str, int]:
        result = await self.db.execute(select(Item.kind, func.count(Item.id)).group_by(Item.kind))
        counts = {kind.value: 0 for kind in ItemKind}
        for kind, count in result.all():
            key = kind.value if isinstance(kind, ItemKind) else str(kind)
            counts[key] = int(count)
        return counts

    async def _count_image_assets(self) -> int:
        return await self._count(ImageAsset)

    async def _count_pending_proposals(self) -> int:
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(MetadataProposal)
                .where(MetadataProposal.status == "pending")
            )
            or 0
        )

    async def _count_missing_cover_items(self) -> int:
        has_cover = (
            select(Variant.id)
            .join(Edition, Variant.edition_id == Edition.id)
            .where(
                Edition.item_id == Item.id,
                or_(
                    Variant.cover_image_url.is_not(None),
                    Variant.thumbnail_image_url.is_not(None),
                    Variant.cover_image_key.is_not(None),
                    Variant.thumbnail_image_key.is_not(None),
                ),
            )
            .exists()
        )
        return int(await self.db.scalar(select(func.count()).select_from(Item).where(~has_cover)) or 0)

    async def _count_missing_provider_link_items(self) -> int:
        has_provider_link = exists().where(
            ItemProviderLink.item_id == Item.id,
        )
        return int(
            await self.db.scalar(select(func.count()).select_from(Item).where(~has_provider_link))
            or 0
        )

    async def _provider_link_count(self) -> int:
        counts = await asyncio.gather(
            self._count(ItemProviderLink),
            self._count(SeriesProviderLink),
            self._count(VolumeProviderLink),
            self._count(BundleReleaseProviderLink),
            self._count(ExternalProviderId),
        )
        return sum(counts)

    async def _search_documents(self) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Item).options(
                selectinload(Item.volume).selectinload(Volume.series),
                selectinload(Item.primary_bundle_releases),
                selectinload(Item.editions).selectinload(Edition.variants),
                selectinload(Item.organization_links).selectinload(EntityOrganization.organization),
                selectinload(Item.creator_links).selectinload(EntityPerson.person),
                selectinload(Item.character_appearances).selectinload(CharacterAppearance.character),
                selectinload(Item.story_arc_items).selectinload(StoryArcItem.story_arc),
            )
        )
        return [item_search_document(item) for item in result.scalars().unique()]

    def _record_search_history(self, response: AdminSearchReindexResponse) -> None:
        _SEARCH_HISTORY.appendleft(
            AdminSearchHistoryEntry(
                timestamp=datetime.now(UTC),
                ok=response.ok,
                index_name=response.index_name,
                indexed_documents=response.indexed_documents,
                error=response.error,
            )
        )

    async def _provider_ingest_success_count(self) -> int:
        job_count = await self._count_ingest_jobs("done")
        memory_count = sum(
            1 for entry in self._ingest_history_reader() if entry.status in {"created", "existing"}
        )
        return job_count + memory_count

    async def _provider_ingest_failure_count(self) -> int:
        job_count = await self._count_ingest_jobs("failed")
        memory_count = sum(1 for entry in self._ingest_history_reader() if entry.status == "failed")
        return job_count + memory_count

    async def _count_ingest_jobs(self, status_filter: str) -> int:
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(ProviderIngestJob)
                .where(ProviderIngestJob.status == status_filter)
            )
            or 0
        )