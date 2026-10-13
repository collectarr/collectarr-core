import logging
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS
from app.models import (
    AdminAuditLog,
    AnimeItem,
    BoardGameItem,
    BookItem,
    CatalogItemProposal,
    ComicItem,
    GameItem,
    ImageAsset,
    MangaItem,
    MovieItem,
    MusicItem,
    TvItem,
)
from app.models.base import ItemKind
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminCatalogSummaryResponse,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
)
from app.search.client import SearchClient
from app.search.documents import catalog_search_document
from app.services.typed_values import materialize_typed_values

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
        search_client_cls: type[SearchClient] | None = None,
        duplicate_group_count: Callable[[], Awaitable[int]],
    ) -> None:
        self.db = db
        self.search_client_cls = search_client_cls or SearchClient
        self._duplicate_group_count = duplicate_group_count

    async def catalog_summary(self) -> AdminCatalogSummaryResponse:
        duplicate_groups = await self._duplicate_group_count()
        items_by_kind = await self._item_counts_by_kind()
        return AdminCatalogSummaryResponse(
            items=sum(items_by_kind.values()),
            items_by_kind=items_by_kind,
            series=0,
            volumes=0,
            editions=0,
            variants=await self._count_contained_values(),
            image_assets=await self._count_image_assets(),
            pending_proposals=await self._count_pending_proposals(),
            missing_cover_items=await self._count_missing_cover_items(),
            duplicate_candidate_groups=duplicate_groups,
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
        result = await self.db.execute(
            stmt.options(selectinload(AdminAuditLog.details)).limit(limit)
        )
        return [
            AdminAuditLogResponse(
                id=row.id,
                action=row.action,
                actor_user_id=row.actor_user_id,
                actor_email=row.actor_email,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                details_json=materialize_typed_values(row.details),
                created_at=row.created_at,
            )
            for row in result.scalars()
        ]

    async def _count(self, model: type) -> int:
        return int(await self.db.scalar(select(func.count()).select_from(model)) or 0)

    async def _count_contained_values(self) -> int:
        counts = {
            BookItem: ("printings", "credits", "identifiers", "series_memberships"),
            ComicItem: ("identifiers",),
            MangaItem: ("identifiers",),
            AnimeItem: ("media", "episodes", "identifiers"),
            MovieItem: ("media",),
            TvItem: ("seasons", "media", "episodes", "identifiers"),
            GameItem: ("identifiers",),
            BoardGameItem: ("identifiers",),
            MusicItem: ("discs",),
        }
        total = 0
        for model, fields in counts.items():
            length = sum(
                func.coalesce(func.jsonb_array_length(model.details[field]), 0) for field in fields
            )
            total += int(
                await self.db.scalar(select(func.coalesce(func.sum(length), 0)).select_from(model))
                or 0
            )
        return total

    async def _item_counts_by_kind(self) -> dict[str, int]:
        counts = {kind.value: 0 for kind in ItemKind}
        for definition in CATALOG_KIND_DEFINITIONS:
            counts[definition.kind.value] = await self._count(definition.model)
        return counts

    async def _count_image_assets(self) -> int:
        return await self._count(ImageAsset)

    async def _count_pending_proposals(self) -> int:
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(CatalogItemProposal)
                .where(CatalogItemProposal.status == "pending")
            )
            or 0
        )

    async def _count_missing_cover_items(self) -> int:
        total = 0
        for definition in CATALOG_KIND_DEFINITIONS:
            model = definition.model
            if definition.kind is ItemKind.music:
                continue
            has_cover = or_(
                model.details["cover_image_url"].as_string().is_not(None),
                model.details["thumbnail_image_url"].as_string().is_not(None),
            )
            total += int(
                await self.db.scalar(select(func.count()).select_from(model).where(~has_cover)) or 0
            )
        total += await self._count_missing_cover_items_for_root(
            MusicItem,
            cover_fields=("cover_image_url", "thumbnail_image_url"),
        )
        return total

    async def _count_missing_cover_items_for_root(
        self,
        model: type,
        *,
        cover_fields: tuple[str, str] = ("cover_image_url", "cover_image_key"),
    ) -> int:
        has_cover = or_(*[getattr(model, field).is_not(None) for field in cover_fields])
        return int(
            await self.db.scalar(select(func.count()).select_from(model).where(~has_cover)) or 0
        )

    async def _search_documents(self) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for definition in CATALOG_KIND_DEFINITIONS:
            result = await self.db.execute(select(definition.model))
            documents.extend(catalog_search_document(item) for item in result.scalars().unique())

        return documents

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
