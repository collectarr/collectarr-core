from collections import deque
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from enum import Enum as PythonEnum
import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.physical_formats import (
    PhysicalFormatConfig,
    is_video_item_kind,
    physical_format_for_id,
)
from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.catalog.media_types import media_type_for_kind
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    AdminAuditLog,
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    ImageAsset,
    ImageCacheEntry,
    Item,
    MetadataProposal,
    Organization,
    Person,
    ProviderIngestJob,
    Release,
    Series,
    Tag,
    Variant,
    Volume,
)
from app.models.user import User
from app.providers.base import (
    MetadataProvider,
    NormalizedCredit,
    NormalizedItem,
    NormalizedVariantCover,
)
from app.providers.comicvine import ComicVineProvider
from app.providers.registry import ProviderRegistry
from app.repositories.metadata import MetadataRepository
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminCatalogSummaryResponse,
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminMetadataCorrectionRequest,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    ProviderIngestHistoryEntry,
    ProviderIngestJobCreateRequest,
    ProviderIngestJobResponse,
    ProviderIngestJobRunResponse,
    ProviderIngestJobSummaryResponse,
    ProviderIngestRequest,
    ProviderIngestRetryRequest,
    ProviderIngestResponse,
    MetadataProposalAdminResponse,
    MetadataProposalSummaryResponse,
    ProviderSearchRequest,
    ProviderStatusResponse,
)
from app.schemas.metadata import item_response_from_model
from app.search.client import SearchClient
from app.search.documents import item_search_document
from app.storage.image_cache import ImageCache
from app.storage.images import ImageMirror


_SEARCH_HISTORY: deque[AdminSearchHistoryEntry] = deque(maxlen=20)
_INGEST_HISTORY: deque[ProviderIngestHistoryEntry] = deque(maxlen=50)
_INGEST_HISTORY_SEQUENCE = 0
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


class AdminMetadataService:
    def __init__(self, db: AsyncSession, actor: User | None = None) -> None:
        self.db = db
        self.actor_user_id = actor.id if actor else None
        self.actor_email = actor.email if actor else None
        self.providers = ProviderRegistry()
        self.settings = get_settings()

    async def provider_statuses(self) -> list[ProviderStatusResponse]:
        statuses: list[ProviderStatusResponse] = []
        for provider in self.providers.all():
            capabilities = provider.capabilities
            statuses.append(
                ProviderStatusResponse(
                    name=provider.name,
                    display_name=capabilities.display_name,
                    kind=capabilities.kind.value,
                    supported_kinds=[kind.value for kind in capabilities.supported_kinds],
                    status="live" if provider.is_configured else "stub",
                    is_configured=provider.is_configured,
                    supports_search=capabilities.supports_search,
                    supports_ingest=capabilities.supports_ingest,
                    requires_user_key=capabilities.requires_user_key,
                    non_commercial_only=capabilities.non_commercial_only,
                    allows_redistribution=capabilities.allows_redistribution,
                    allows_image_mirroring=capabilities.allows_image_mirroring,
                    requires_attribution=capabilities.requires_attribution,
                    license_name=capabilities.license_name,
                    terms_url=capabilities.terms_url,
                    attribution_url=capabilities.attribution_url,
                    rate_limit=capabilities.rate_limit,
                    cache_policy=capabilities.cache_policy,
                    message=provider.status_message,
                )
            )
        return statuses

    async def catalog_summary(self) -> AdminCatalogSummaryResponse:
        duplicate_groups = await self._duplicate_group_count()
        return AdminCatalogSummaryResponse(
            items=await self._count(Item),
            series=await self._count(Series),
            volumes=await self._count(Volume),
            editions=await self._count(Edition),
            variants=await self._count(Variant),
            releases=await self._count(Release),
            provider_links=await self._count(ExternalProviderId),
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
            client = SearchClient()
            client.client.health()
            stats = client.client.index(client.index_name).get_stats()
            document_count = _meili_document_count(stats)
        except Exception as exc:
            logger.warning("admin_search_status_failed error=%s", exc)
            return AdminSearchStatusResponse(
                ok=False,
                index_name=SearchClient.index_name,
                error=str(exc),
            )
        return AdminSearchStatusResponse(
            ok=True,
            index_name=client.index_name,
            document_count=document_count,
            is_empty=document_count == 0 if document_count is not None else None,
        )

    async def reindex_search(self) -> AdminSearchReindexResponse:
        search = SearchClient()
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

    async def catalog_items(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        limit: int = 25,
    ) -> list[Any]:
        items = await MetadataRepository(self.db).search_items(
            query=query,
            kind=kind,
            limit=limit,
        )
        return [item_response_from_model(item) for item in items]

    async def update_catalog_item(
        self,
        item_id: UUID,
        payload: AdminMetadataCorrectionRequest,
        kind: ItemKind | None = None,
    ) -> Any:
        item = await MetadataRepository(self.db).get_item(item_id, kind)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail="Item not found",
            )
        update_data = payload.model_dump(exclude_unset=True)
        before = {
            "title": item.title,
            "item_number": item.item_number,
            "synopsis": item.synopsis,
            "page_count": item.page_count,
        }
        if "title" in update_data and payload.title is not None:
            item.title = payload.title
        if "item_number" in update_data:
            item.item_number = payload.item_number
        if "synopsis" in update_data:
            item.synopsis = payload.synopsis
        if "page_count" in update_data:
            item.page_count = payload.page_count
        item.sort_key = self._sort_key(item.kind, item.title, item.item_number)

        edition = self._primary_edition_model(item)
        physical_format = None
        if "physical_format" in update_data:
            physical_format = self._validated_physical_format(
                item.kind,
                payload.physical_format,
            )
        if edition is not None:
            if "publisher" in update_data:
                edition.publisher = payload.publisher
            if "release_date" in update_data:
                edition.release_date = payload.release_date
            if physical_format is not None:
                self._apply_physical_format_to_edition(edition, physical_format)

        variant = self._primary_variant_model(item)
        if variant is not None:
            if "variant_name" in update_data and payload.variant_name is not None:
                variant.name = payload.variant_name
            if "barcode" in update_data:
                variant.barcode = payload.barcode
            if "cover_image_url" in update_data:
                variant.cover_image_url = payload.cover_image_url
                variant.metadata_json = self._metadata_with_cover(
                    variant.metadata_json,
                    payload.cover_image_url,
                )
            if "thumbnail_image_url" in update_data:
                variant.thumbnail_image_url = payload.thumbnail_image_url
            if physical_format is not None:
                self._apply_physical_format_to_variant(variant, physical_format)

        metadata = dict(item.metadata_json or {})
        metadata["admin_corrected_at"] = datetime.now(UTC).isoformat()
        metadata["admin_corrected_fields"] = sorted(update_data.keys())
        item.metadata_json = metadata
        self._record_admin_audit(
            action="metadata.correction",
            entity_type="item",
            entity_id=item.id,
            details={
                "kind": item.kind,
                "fields": sorted(update_data.keys()),
                "before": before,
                "after": update_data,
            },
        )
        await self.db.commit()
        loaded_item = await MetadataRepository(self.db).get_item(item.id)
        if loaded_item:
            await SearchClient().index_documents_best_effort([item_search_document(loaded_item)])
        return item_response_from_model(loaded_item)

    def _validated_physical_format(
        self,
        kind: ItemKind,
        physical_format: str | None,
    ) -> PhysicalFormatConfig:
        if not physical_format:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="physical_format_required",
                detail="physical_format is required when updating a video format",
            )
        if not is_video_item_kind(kind):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="physical_format_unsupported",
                detail="physical_format is only supported for movie and TV catalog items",
            )
        config = physical_format_for_id(physical_format)
        if config is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="invalid_physical_format",
                detail="physical_format must be one of DVD, Blu-ray, 4K UHD, VHS, LaserDisc, or digital",
            )
        return config

    def _apply_physical_format_to_edition(
        self,
        edition: Edition,
        physical_format: PhysicalFormatConfig,
    ) -> None:
        edition.format = physical_format.label
        metadata = self._metadata_with_physical_format(
            edition.metadata_json,
            physical_format,
        )
        edition.metadata_json = metadata

    def _apply_physical_format_to_variant(
        self,
        variant: Variant,
        physical_format: PhysicalFormatConfig,
    ) -> None:
        variant.variant_type = physical_format.variant_type
        metadata = self._metadata_with_physical_format(
            variant.metadata_json,
            physical_format,
        )
        variant.metadata_json = metadata

    def _metadata_with_physical_format(
        self,
        metadata_json: dict[str, Any] | None,
        physical_format: PhysicalFormatConfig,
    ) -> dict[str, Any]:
        metadata = dict(metadata_json or {})
        normalized_source = metadata.get("normalized")
        normalized = dict(normalized_source) if isinstance(normalized_source, dict) else {}
        normalized.update(
            {
                "physical_format": physical_format.id,
                "physical_format_label": physical_format.label,
                "physical_format_media_family": physical_format.media_family,
                "physical_format_variant_type": physical_format.variant_type,
            }
        )
        metadata["normalized"] = normalized
        return metadata

    def _metadata_with_cover(
        self,
        metadata_json: dict[str, Any] | None,
        source_url: str | None,
    ) -> dict[str, Any]:
        metadata = dict(metadata_json or {})
        normalized_source = metadata.get("normalized")
        normalized = dict(normalized_source) if isinstance(normalized_source, dict) else {}
        normalized.update(self._cover_metadata(source_url, None))
        metadata["normalized"] = normalized
        return metadata

    async def duplicate_candidates(self, limit: int = 10) -> list[AdminDuplicateCandidateResponse]:
        count_label = func.count(Item.id).label("count")
        item_ids_label = func.array_agg(Item.id).label("item_ids")
        result = await self.db.execute(
            select(
                Item.kind,
                Item.title,
                Item.item_number,
                count_label,
                item_ids_label,
            )
            .group_by(Item.kind, Item.title, Item.item_number)
            .having(func.count(Item.id) > 1)
            .order_by(count_label.desc(), Item.title.asc())
            .limit(min(limit * 4, 200))
        )
        candidates: list[AdminDuplicateCandidateResponse] = []
        for kind, title, item_number, count, item_ids in result.all():
            ids = list(item_ids or [])
            if await self._duplicate_group_is_ignored(ids):
                continue
            conflicts = await self._duplicate_conflict_flags(ids)
            candidates.append(
                AdminDuplicateCandidateResponse(
                    kind=kind.value if hasattr(kind, "value") else str(kind),
                    title=title,
                    item_number=item_number,
                    count=count,
                    item_ids=ids,
                    reason="same title and item number",
                    has_provider_conflicts=conflicts["provider"],
                    has_cover_conflicts=conflicts["cover"],
                )
            )
            if len(candidates) >= limit:
                break
        return candidates

    async def ignore_duplicate_candidate(
        self, payload: AdminDuplicateIgnoreRequest
    ) -> AdminDuplicateActionResponse:
        items = await self._items_by_ids(payload.item_ids)
        if len(items) != len(set(payload.item_ids)):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="duplicate_item_not_found",
                detail="One or more duplicate items were not found",
            )
        self._ensure_same_duplicate_group(items)
        token = self._duplicate_ignore_token([item.id for item in items])
        for item in items:
            metadata = dict(item.metadata_json or {})
            metadata["admin_duplicate_ignore_token"] = token
            metadata["admin_duplicate_ignored_at"] = datetime.now(UTC).isoformat()
            item.metadata_json = metadata
        self._record_admin_audit(
            action="duplicates.ignore",
            entity_type="duplicate_group",
            details={
                "item_ids": [item.id for item in items],
                "kind": items[0].kind if items else None,
                "title": items[0].title if items else None,
                "item_number": items[0].item_number if items else None,
            },
        )
        await self.db.commit()
        return AdminDuplicateActionResponse(ok=True, affected_items=len(items))

    async def merge_duplicate_candidate(
        self, payload: AdminDuplicateMergeRequest
    ) -> AdminDuplicateActionResponse:
        source_ids = [
            item_id for item_id in payload.source_item_ids if item_id != payload.target_item_id
        ]
        if not source_ids:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_source_required",
                detail="At least one source item different from target_item_id is required",
            )
        items = await self._items_by_ids([payload.target_item_id, *source_ids])
        if len(items) != len({payload.target_item_id, *source_ids}):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="duplicate_item_not_found",
                detail="One or more duplicate items were not found",
            )
        target = next(item for item in items if item.id == payload.target_item_id)
        sources = [item for item in items if item.id != payload.target_item_id]
        self._ensure_same_duplicate_group([target, *sources])

        for source in sources:
            await self._move_item_children(source.id, target.id)
            await self.db.delete(source)
        self._record_admin_audit(
            action="duplicates.merge",
            entity_type="item",
            entity_id=target.id,
            details={
                "target_item_id": target.id,
                "source_item_ids": [source.id for source in sources],
                "kind": target.kind,
                "title": target.title,
                "item_number": target.item_number,
            },
        )
        await self.db.commit()

        loaded_item = await MetadataRepository(self.db).get_item(target.id)
        if loaded_item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="merged_target_unavailable",
                detail="Merged target item could not be loaded",
            )
        return AdminDuplicateActionResponse(
            ok=True,
            affected_items=len(sources),
            item=item_response_from_model(loaded_item),
        )

    async def provider_search(self, payload: ProviderSearchRequest) -> list[dict[str, Any]]:
        provider = self._provider(payload.provider)
        if not provider.capabilities.supports_search:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_search_unsupported",
                detail=f"Provider '{payload.provider.value}' does not support search",
            )
        if payload.kind is not None and not provider.capabilities.supports_kind(payload.kind):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_kind_unsupported",
                detail=(
                    f"Provider '{payload.provider.value}' does not support "
                    f"kind '{payload.kind.value}'"
                ),
            )
        results = await provider.search(payload.query, payload.kind)
        return [result.__dict__ for result in results]

    async def proposal_summary(self) -> MetadataProposalSummaryResponse:
        result = await self.db.execute(
            select(MetadataProposal.status, func.count(MetadataProposal.id)).group_by(
                MetadataProposal.status
            )
        )
        counts = {status: count for status, count in result.all()}
        pending = counts.get("pending", 0)
        approved = counts.get("approved", 0)
        rejected = counts.get("rejected", 0)
        return MetadataProposalSummaryResponse(
            pending=pending,
            approved=approved,
            rejected=rejected,
            total=pending + approved + rejected,
        )

    async def list_proposals(
        self, status_filter: str = "pending", provider_filter: ExternalProvider | None = None
    ) -> list[MetadataProposalAdminResponse]:
        stmt = select(MetadataProposal).where(MetadataProposal.status == status_filter)
        if provider_filter:
            stmt = stmt.where(MetadataProposal.provider == provider_filter)
        result = await self.db.execute(stmt.order_by(MetadataProposal.created_at.asc()))
        return [
            MetadataProposalAdminResponse.model_validate(proposal) for proposal in result.scalars()
        ]

    async def approve_proposal(self, proposal_id: UUID) -> ProviderIngestResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_proposal_not_found",
                detail="Proposal not found",
            )
        if proposal.provider_item_id is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="metadata_proposal_missing_provider_item",
                detail="Proposal does not have a provider item id",
            )
        response = await self.ingest(
            ProviderIngestRequest(
                provider=proposal.provider,
                provider_item_id=proposal.provider_item_id,
            )
        )
        proposal.status = "approved"
        self._record_admin_audit(
            action="metadata_proposal.approve",
            entity_type="metadata_proposal",
            entity_id=proposal.id,
            details={
                "provider": proposal.provider,
                "provider_item_id": proposal.provider_item_id,
                "item_id": response.item_id,
                "created": response.created,
            },
        )
        await self.db.commit()
        return response

    async def approve_proposal_with_provider_item(
        self,
        proposal_id: UUID,
        payload: ProviderIngestRequest,
    ) -> ProviderIngestResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_proposal_not_found",
                detail="Proposal not found",
            )
        response = await self.ingest(payload)
        proposal.provider = payload.provider
        proposal.provider_item_id = payload.provider_item_id
        proposal.status = "approved"
        self._record_admin_audit(
            action="metadata_proposal.approve_provider",
            entity_type="metadata_proposal",
            entity_id=proposal.id,
            details={
                "provider": payload.provider,
                "provider_item_id": payload.provider_item_id,
                "item_id": response.item_id,
                "created": response.created,
            },
        )
        await self.db.commit()
        return response

    async def reject_proposal(self, proposal_id: UUID) -> MetadataProposalAdminResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_proposal_not_found",
                detail="Proposal not found",
            )
        proposal.status = "rejected"
        self._record_admin_audit(
            action="metadata_proposal.reject",
            entity_type="metadata_proposal",
            entity_id=proposal.id,
            details={
                "provider": proposal.provider,
                "provider_item_id": proposal.provider_item_id,
                "query": proposal.query,
            },
        )
        await self.db.commit()
        await self.db.refresh(proposal)
        return MetadataProposalAdminResponse.model_validate(proposal)

    async def create_ingest_job(
        self,
        payload: ProviderIngestJobCreateRequest,
    ) -> ProviderIngestJobResponse:
        provider = self._provider(payload.provider)
        self._ensure_provider_ingest_supported(provider, payload.provider)
        job = ProviderIngestJob(
            provider=payload.provider,
            provider_item_id=payload.provider_item_id,
            status="queued",
            attempts=0,
            max_attempts=payload.max_attempts,
            next_run_at=datetime.now(UTC),
        )
        self.db.add(job)
        await self.db.flush()
        self._record_admin_audit(
            action="provider_ingest.job_create",
            entity_type="provider_ingest_job",
            entity_id=job.id,
            details={
                "provider": payload.provider,
                "provider_item_id": payload.provider_item_id,
                "max_attempts": payload.max_attempts,
            },
        )
        await self.db.commit()
        await self.db.refresh(job)
        return ProviderIngestJobResponse.model_validate(job)

    async def ingest_jobs(
        self,
        status_filter: str | None = None,
        limit: int = 25,
        provider_filter: ExternalProvider | None = None,
        query: str | None = None,
    ) -> list[ProviderIngestJobResponse]:
        stmt = select(ProviderIngestJob).order_by(
            ProviderIngestJob.created_at.desc(),
            ProviderIngestJob.id.desc(),
        )
        if status_filter:
            stmt = stmt.where(ProviderIngestJob.status == status_filter)
        if provider_filter:
            stmt = stmt.where(ProviderIngestJob.provider == provider_filter)
        normalized_query = " ".join(query.split()) if query else ""
        if normalized_query:
            pattern = f"%{normalized_query}%"
            stmt = stmt.where(
                or_(
                    ProviderIngestJob.provider_item_id.ilike(pattern),
                    ProviderIngestJob.last_error.ilike(pattern),
                )
            )
        result = await self.db.execute(stmt.limit(limit))
        return [ProviderIngestJobResponse.model_validate(job) for job in result.scalars().all()]

    async def ingest_job_summary(self) -> ProviderIngestJobSummaryResponse:
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(
            seconds=self.settings.worker_provider_ingest_stale_after_seconds
        )
        counts_result = await self.db.execute(
            select(ProviderIngestJob.status, func.count())
            .select_from(ProviderIngestJob)
            .group_by(ProviderIngestJob.status)
        )
        counts = {
            "queued": 0,
            "running": 0,
            "failed": 0,
            "done": 0,
        }
        for status_value, count in counts_result.all():
            if status_value in counts:
                counts[status_value] = int(count)

        due_queued = await self.db.scalar(
            select(func.count())
            .select_from(ProviderIngestJob)
            .where(
                ProviderIngestJob.status == "queued",
                or_(
                    ProviderIngestJob.next_run_at.is_(None),
                    ProviderIngestJob.next_run_at <= now,
                ),
            )
        )
        stale_running = await self.db.scalar(
            select(func.count())
            .select_from(ProviderIngestJob)
            .where(
                ProviderIngestJob.status == "running",
                ProviderIngestJob.updated_at < stale_cutoff,
            )
        )
        oldest_queued_at = await self.db.scalar(
            select(func.min(ProviderIngestJob.created_at)).where(
                ProviderIngestJob.status == "queued"
            )
        )
        next_run_at = await self.db.scalar(
            select(func.min(ProviderIngestJob.next_run_at)).where(
                ProviderIngestJob.status == "queued",
                ProviderIngestJob.next_run_at.is_not(None),
            )
        )
        latest_failure_at = await self.db.scalar(
            select(func.max(ProviderIngestJob.updated_at)).where(
                ProviderIngestJob.status == "failed"
            )
        )
        return ProviderIngestJobSummaryResponse(
            **counts,
            due_queued=int(due_queued or 0),
            stale_running=int(stale_running or 0),
            oldest_queued_at=oldest_queued_at,
            next_run_at=next_run_at,
            latest_failure_at=latest_failure_at,
        )

    async def run_ingest_job(self, job_id: UUID) -> ProviderIngestJobResponse:
        job = await self.db.get(ProviderIngestJob, job_id)
        if job is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="provider_ingest_job_not_found",
                detail="Ingest job not found",
            )
        if job.status == "running":
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="provider_ingest_job_running",
                detail="Ingest job is already running",
            )
        executed = await self._execute_ingest_job(job)
        self._record_admin_audit(
            action="provider_ingest.job_run",
            entity_type="provider_ingest_job",
            entity_id=executed.id,
            details=self._ingest_job_audit_details(executed),
        )
        await self.db.commit()
        return ProviderIngestJobResponse.model_validate(executed)

    async def retry_ingest_job(self, job_id: UUID) -> ProviderIngestJobResponse:
        job = await self.db.get(ProviderIngestJob, job_id)
        if job is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="provider_ingest_job_not_found",
                detail="Ingest job not found",
            )
        if job.status == "running":
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="provider_ingest_job_running",
                detail="Ingest job is already running",
            )
        job.status = "queued"
        job.next_run_at = datetime.now(UTC)
        job.last_error = None
        await self.db.commit()
        await self.db.refresh(job)
        executed = await self._execute_ingest_job(job)
        self._record_admin_audit(
            action="provider_ingest.job_retry",
            entity_type="provider_ingest_job",
            entity_id=executed.id,
            details=self._ingest_job_audit_details(executed),
        )
        await self.db.commit()
        return ProviderIngestJobResponse.model_validate(executed)

    async def run_pending_ingest_jobs(self, limit: int = 5) -> ProviderIngestJobRunResponse:
        recovered = await self.recover_stale_ingest_jobs()
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(ProviderIngestJob)
            .where(
                ProviderIngestJob.status == "queued",
                or_(
                    ProviderIngestJob.next_run_at.is_(None),
                    ProviderIngestJob.next_run_at <= now,
                ),
            )
            .order_by(ProviderIngestJob.created_at.asc())
            .limit(limit)
        )
        processed: list[ProviderIngestJobResponse] = []
        for job in result.scalars().all():
            processed.append(
                ProviderIngestJobResponse.model_validate(await self._execute_ingest_job(job))
            )
        if self.actor_user_id is not None:
            self._record_admin_audit(
                action="provider_ingest.jobs_run_pending",
                entity_type="provider_ingest_queue",
                details={
                    "processed": len(processed),
                    "recovered": recovered,
                    "job_ids": [job.id for job in processed],
                },
            )
            await self.db.commit()
        return ProviderIngestJobRunResponse(
            processed=len(processed),
            jobs=processed,
            recovered=recovered,
        )

    async def recover_stale_ingest_jobs(self) -> int:
        stale_after = self.settings.worker_provider_ingest_stale_after_seconds
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_after)
        result = await self.db.execute(
            update(ProviderIngestJob)
            .where(
                ProviderIngestJob.status == "running",
                ProviderIngestJob.updated_at < cutoff,
            )
            .values(
                status="queued",
                next_run_at=datetime.now(UTC),
                last_error="Recovered stale running ingest job",
            )
            .returning(ProviderIngestJob.id)
        )
        recovered = len(result.scalars().all())
        if recovered:
            await self.db.commit()
            logger.warning("provider_ingest_jobs_recovered count=%s", recovered)
        return recovered

    def ingest_history(self) -> list[ProviderIngestHistoryEntry]:
        return list(_INGEST_HISTORY)

    async def retry_ingest(self, payload: ProviderIngestRetryRequest) -> ProviderIngestResponse:
        entry = next(
            (entry for entry in _INGEST_HISTORY if entry.id == payload.history_id),
            None,
        )
        if entry is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="provider_ingest_history_not_found",
                detail="Provider ingest history entry not found",
            )
        if entry.status != "failed":
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_ingest_history_not_failed",
                detail="Only failed provider ingest entries can be retried",
            )
        response = await self.ingest(
            ProviderIngestRequest(
                provider=entry.provider,
                provider_item_id=entry.provider_item_id,
            )
        )
        self._record_admin_audit(
            action="provider_ingest.history_retry",
            entity_type="provider_ingest_history",
            details={
                "history_id": entry.id,
                "provider": entry.provider,
                "provider_item_id": entry.provider_item_id,
                "item_id": response.item_id,
                "created": response.created,
            },
        )
        await self.db.commit()
        return response

    async def ingest(self, payload: ProviderIngestRequest) -> ProviderIngestResponse:
        attempts = max(1, self.settings.provider_ingest_retry_attempts + 1)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await self._ingest_once(payload)
                self._record_ingest_history(
                    payload=payload,
                    status="created" if response.created else "existing",
                    attempts=attempt,
                    item_id=response.item_id,
                )
                logger.info(
                    "provider_ingest_finished provider=%s provider_item_id=%s status=%s "
                    "attempts=%s item_id=%s",
                    payload.provider.value,
                    payload.provider_item_id,
                    "created" if response.created else "existing",
                    attempt,
                    response.item_id,
                )
                return response
            except Exception as exc:
                last_error = exc
                await self.db.rollback()
                if attempt >= attempts or not self._is_retryable_ingest_error(exc):
                    self._record_ingest_history(
                        payload=payload,
                        status="failed",
                        attempts=attempt,
                        error=self._error_message(exc),
                    )
                    logger.warning(
                        "provider_ingest_failed provider=%s provider_item_id=%s attempts=%s "
                        "error=%s",
                        payload.provider.value,
                        payload.provider_item_id,
                        attempt,
                        self._error_message(exc),
                    )
                    raise
        raise RuntimeError("Provider ingest retry loop exited unexpectedly") from last_error

    async def _ingest_once(self, payload: ProviderIngestRequest) -> ProviderIngestResponse:
        provider = self._provider(payload.provider)
        self._ensure_provider_ingest_supported(provider, payload.provider)
        existing_provider_id = await self._get_provider_id(payload)
        if existing_provider_id:
            return await self._existing_response(existing_provider_id)

        provider_item = await provider.get_item(payload.provider_item_id)
        existing_provider_id = await self._get_provider_id_value(
            payload.provider, provider_item.provider_item_id
        )
        if existing_provider_id:
            return await self._existing_response(existing_provider_id)

        normalized = await provider.normalize(
            dict(provider_item.raw) | {"id": provider_item.provider_item_id}
        )
        normalized = await self._enrich_missing_comic_cover(normalized)
        physical_format = self._physical_format_for_normalized(normalized)
        edition_format = physical_format.label if physical_format else normalized.edition_format
        variant_name = normalized.variant_name or (
            physical_format.label if physical_format is not None else "Cover A"
        )
        variant_type = normalized.variant_type or (
            physical_format.variant_type if physical_format is not None else None
        )
        mirrored_cover = None
        if self._should_mirror_provider_images(provider):
            mirrored_cover = await ImageMirror().mirror_cover_best_effort(
                normalized.cover_image_url,
                payload.provider.value,
                provider_item.provider_item_id,
            )
        cover_metadata = self._cover_metadata(
            normalized.cover_image_url,
            mirrored_cover,
        )
        volume = await self._upsert_volume(
            normalized.kind,
            normalized.series_title,
            normalized.volume_name,
            normalized.volume_start_year,
        )
        item = Item(
            volume=volume,
            kind=normalized.kind,
            title=normalized.title,
            item_number=normalized.item_number,
            sort_key=self._sort_key(normalized.kind, normalized.title, normalized.item_number),
            synopsis=normalized.synopsis,
            runtime_minutes=normalized.runtime_minutes,
            page_count=normalized.page_count,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "normalized": {
                    "kind": normalized.kind.value,
                    "series_title": normalized.series_title,
                    "volume_name": normalized.volume_name,
                    "volume_number": normalized.volume_number,
                    "volume_start_year": normalized.volume_start_year,
                    "runtime_minutes": normalized.runtime_minutes,
                    "story_arcs": [credit.name for credit in normalized.story_arcs],
                    **cover_metadata,
                },
            },
        )
        edition = Edition(
            item=item,
            title=normalized.edition_title or "Standard Edition",
            format=edition_format,
            publisher=normalized.publisher,
            isbn=normalized.isbn,
            release_date=normalized.release_date,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "normalized": {
                    "title": normalized.edition_title or "Standard Edition",
                    "format": edition_format,
                    "physical_format": physical_format.id if physical_format else None,
                    "physical_format_label": physical_format.label if physical_format else None,
                    "physical_format_media_family": (
                        physical_format.media_family if physical_format else None
                    ),
                    "physical_format_variant_type": (
                        physical_format.variant_type if physical_format else None
                    ),
                    "publisher": normalized.publisher,
                    "release_date": (
                        normalized.release_date.isoformat() if normalized.release_date else None
                    ),
                    "isbn": normalized.isbn,
                    "barcode": normalized.barcode,
                    "creators": [
                        {"name": credit.name, "role": credit.role} for credit in normalized.creators
                    ],
                    "characters": [credit.name for credit in normalized.characters],
                    "story_arcs": [credit.name for credit in normalized.story_arcs],
                    **cover_metadata,
                },
                "source": provider_item.raw,
            },
        )
        variant = Variant(
            edition=edition,
            name=variant_name,
            variant_type=variant_type,
            barcode=normalized.barcode,
            isbn=normalized.isbn,
            cover_price_cents=normalized.cover_price_cents,
            currency=normalized.currency,
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            thumbnail_image_key=mirrored_cover.thumbnail_key if mirrored_cover else None,
            thumbnail_image_url=mirrored_cover.thumbnail_url if mirrored_cover else None,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "normalized": {
                    "name": variant_name,
                    "variant_type": variant_type,
                    "physical_format": physical_format.id if physical_format else None,
                    "physical_format_label": physical_format.label if physical_format else None,
                    "physical_format_media_family": (
                        physical_format.media_family if physical_format else None
                    ),
                    "physical_format_variant_type": (
                        physical_format.variant_type if physical_format else None
                    ),
                    "barcode": normalized.barcode,
                    "isbn": normalized.isbn,
                    "cover_price_cents": normalized.cover_price_cents,
                    "currency": normalized.currency,
                    **cover_metadata,
                },
            },
            is_primary=True,
        )
        additional_variants, additional_mirrored_covers = await self._comicvine_associated_variants(
            provider=provider,
            provider_name=payload.provider,
            provider_item_id=provider_item.provider_item_id,
            normalized=normalized,
            edition=edition,
            primary_cover_url=normalized.cover_image_url,
        )
        release = Release(
            edition=edition,
            region="US",
            release_date=normalized.release_date,
            publisher=normalized.publisher,
            external_ids=normalized.provider_ids,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "normalized": {
                    "release_date": (
                        normalized.release_date.isoformat() if normalized.release_date else None
                    ),
                    "publisher": normalized.publisher,
                    "external_ids": normalized.provider_ids,
                },
            },
        )
        self.db.add_all([item, edition, variant, *additional_variants, release])
        await self.db.flush()
        if mirrored_cover:
            await ImageCache(self.db).record_mirrored_cover(mirrored_cover)
        for mirrored_variant_cover in additional_mirrored_covers:
            await ImageCache(self.db).record_mirrored_cover(mirrored_variant_cover)
        await self._add_provider_links(payload.provider, normalized.provider_ids, "item", item.id)
        if volume:
            await self._add_provider_links(
                payload.provider, normalized.volume_provider_ids, "volume", volume.id
            )
        await self._link_publisher(item.id, normalized.publisher)
        await self._link_people(item.id, normalized.creators)
        await self._link_tags(item.id, "character", normalized.characters)
        await self._link_tags(item.id, "story_arc", normalized.story_arcs)
        await self.db.commit()
        loaded_item = await MetadataRepository(self.db).get_item(item.id)
        if loaded_item:
            await SearchClient().index_documents_best_effort([item_search_document(loaded_item)])
        return ProviderIngestResponse(
            item_id=item.id,
            created=True,
            item=item_response_from_model(loaded_item),
        )

    def _physical_format_for_normalized(
        self,
        normalized: NormalizedItem,
    ) -> PhysicalFormatConfig | None:
        if not is_video_item_kind(normalized.kind):
            return None
        candidate = normalized.physical_format or normalized.edition_format
        if not candidate:
            return None
        return physical_format_for_id(candidate)

    async def _comicvine_associated_variants(
        self,
        *,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
        provider_item_id: str,
        normalized: NormalizedItem,
        edition: Edition,
        primary_cover_url: str | None,
    ) -> tuple[list[Variant], list[Any]]:
        if not normalized.variant_covers:
            return [], []

        variants: list[Variant] = []
        mirrored_covers: list[Any] = []
        seen_cover_urls = {primary_cover_url} if primary_cover_url else set()
        for cover in normalized.variant_covers:
            if not cover.cover_image_url or cover.cover_image_url in seen_cover_urls:
                continue
            seen_cover_urls.add(cover.cover_image_url)

            mirrored_cover = None
            if self._should_mirror_provider_images(provider):
                mirrored_cover = await ImageMirror().mirror_cover_best_effort(
                    cover.cover_image_url,
                    provider_name.value,
                    provider_item_id,
                )
            if mirrored_cover is not None:
                mirrored_covers.append(mirrored_cover)

            cover_metadata = self._cover_metadata(cover.cover_image_url, mirrored_cover)
            variants.append(
                Variant(
                    edition=edition,
                    name=self._variant_cover_name(cover, len(variants) + 1),
                    variant_type="variant",
                    cover_image_key=mirrored_cover.key if mirrored_cover else None,
                    cover_image_url=(
                        mirrored_cover.url if mirrored_cover else cover.cover_image_url
                    ),
                    thumbnail_image_key=(mirrored_cover.thumbnail_key if mirrored_cover else None),
                    thumbnail_image_url=(
                        mirrored_cover.thumbnail_url
                        if mirrored_cover
                        else cover.thumbnail_image_url
                    ),
                    description=cover.caption,
                    metadata_json={
                        "provider": provider_name.value,
                        "provider_item_id": cover.provider_item_id or provider_item_id,
                        "normalized": {
                            "name": self._variant_cover_name(cover, len(variants) + 1),
                            "variant_type": "variant",
                            "associated_image_id": cover.source_id,
                            "caption": cover.caption,
                            **cover_metadata,
                        },
                    },
                    is_primary=False,
                )
            )
        return variants, mirrored_covers

    def _variant_cover_name(self, cover: NormalizedVariantCover, index: int) -> str:
        name = cover.name.strip() if cover.name else ""
        return name[:255] if name else f"Variant cover {index}"

    def _cover_metadata(
        self,
        source_url: str | None,
        mirrored_cover: Any | None,
    ) -> dict[str, Any]:
        if mirrored_cover is not None:
            return {
                "cover_status": "mirrored",
                "cover_source_url": source_url,
                "cover_delivery_url": mirrored_cover.url,
                "cover_storage": "object_storage",
                "cover_policy": "minio_mirror",
            }
        if source_url:
            return {
                "cover_status": "external_url",
                "cover_source_url": source_url,
                "cover_delivery_url": source_url,
                "cover_storage": "provider_external_url",
                "cover_policy": "external_url_default",
            }
        return {
            "cover_status": "missing",
            "cover_source_url": None,
            "cover_delivery_url": None,
            "cover_storage": "generated_client_fallback",
            "cover_policy": "generated_cover_fallback",
        }

    async def _enrich_missing_comic_cover(
        self,
        normalized: NormalizedItem,
    ) -> NormalizedItem:
        if normalized.cover_image_url or normalized.kind not in {
            ItemKind.comic,
            ItemKind.manga,
        }:
            return normalized
        if normalized.variant_type == "variant":
            return normalized
        issue_number = normalized.item_number
        series_title = normalized.series_title or normalized.title
        if not issue_number or not series_title:
            return normalized
        try:
            provider = self.providers.get("comicvine")
        except KeyError:
            return normalized
        if not isinstance(provider, ComicVineProvider) or not provider.is_configured:
            return normalized
        try:
            cover = await provider.find_issue_cover(
                series_title=series_title,
                issue_number=issue_number,
                start_year=normalized.volume_start_year,
            )
        except Exception:
            logger.warning(
                "comicvine_cover_enrichment_failed series=%s issue=%s",
                series_title,
                issue_number,
                exc_info=True,
            )
            return normalized
        if cover is None:
            return normalized
        return replace(
            normalized,
            cover_image_url=cover.image_url,
            provider_ids={
                **normalized.provider_ids,
                "comicvine": cover.provider_item_id,
            },
        )

    async def _execute_ingest_job(self, job: ProviderIngestJob) -> ProviderIngestJob:
        job_id = job.id
        provider = job.provider
        provider_item_id = job.provider_item_id
        job.status = "running"
        job.attempts += 1
        job.last_error = None
        job.next_run_at = None
        await self.db.commit()
        try:
            response = await self.ingest(
                ProviderIngestRequest(
                    provider=provider,
                    provider_item_id=provider_item_id,
                )
            )
        except Exception as exc:
            await self.db.rollback()
            refreshed = await self.db.get(ProviderIngestJob, job_id)
            if refreshed is None:
                raise
            refreshed.last_error = self._error_message(exc)
            if refreshed.attempts < refreshed.max_attempts and self._is_retryable_ingest_error(exc):
                refreshed.status = "queued"
                refreshed.next_run_at = datetime.now(UTC) + self._backoff_delay(refreshed.attempts)
            else:
                refreshed.status = "failed"
                refreshed.next_run_at = None
            await self.db.commit()
            await self.db.refresh(refreshed)
            logger.warning(
                "provider_ingest_job_failed job_id=%s provider=%s provider_item_id=%s "
                "status=%s attempts=%s error=%s",
                refreshed.id,
                refreshed.provider.value,
                refreshed.provider_item_id,
                refreshed.status,
                refreshed.attempts,
                refreshed.last_error,
            )
            return refreshed

        refreshed = await self.db.get(ProviderIngestJob, job_id)
        if refreshed is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="provider_ingest_job_not_found",
                detail="Ingest job disappeared during execution",
            )
        refreshed.status = "done"
        refreshed.item_id = response.item_id
        refreshed.last_error = None
        refreshed.next_run_at = None
        await self.db.commit()
        await self.db.refresh(refreshed)
        logger.info(
            "provider_ingest_job_finished job_id=%s provider=%s provider_item_id=%s item_id=%s",
            refreshed.id,
            refreshed.provider.value,
            refreshed.provider_item_id,
            refreshed.item_id,
        )
        return refreshed

    def _provider(self, provider: ExternalProvider) -> MetadataProvider:
        try:
            return self.providers.get(provider.value)
        except KeyError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_not_configured",
                detail=f"Provider '{provider.value}' is not configured",
            ) from exc

    def _ensure_provider_ingest_supported(
        self,
        provider: MetadataProvider,
        provider_name: ExternalProvider,
    ) -> None:
        if provider.capabilities.supports_ingest:
            return
        raise ApiHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="provider_ingest_unsupported",
            detail=f"Provider '{provider_name.value}' does not support catalog ingest yet",
        )

    def _should_mirror_provider_images(self, provider: MetadataProvider) -> bool:
        if not self.settings.mirror_provider_images:
            return False
        if self.settings.mirror_provider_images_allow_restricted:
            return True
        return provider.capabilities.allows_image_mirroring

    async def _get_provider_id(self, payload: ProviderIngestRequest) -> ExternalProviderId | None:
        return await self._get_provider_id_value(payload.provider, payload.provider_item_id)

    async def _get_provider_id_value(
        self, provider: ExternalProvider, provider_item_id: str
    ) -> ExternalProviderId | None:
        result = await self.db.execute(
            select(ExternalProviderId).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
            )
        )
        return result.scalar_one_or_none()

    async def _existing_response(self, provider_id: ExternalProviderId) -> ProviderIngestResponse:
        item = await MetadataRepository(self.db).get_item(provider_id.entity_id)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="provider_link_stale",
                detail="Provider link is stale",
            )
        return ProviderIngestResponse(
            item_id=item.id,
            created=False,
            item=item_response_from_model(item),
        )

    async def _upsert_volume(
        self,
        kind: ItemKind,
        series_title: str | None,
        volume_name: str | None,
        volume_start_year: int | None,
    ) -> Volume | None:
        if not series_title and not volume_name:
            return None

        title = series_title or volume_name or "Unknown Series"
        series = await self._get_or_create_series(kind, title)
        name = volume_name or title
        result = await self.db.execute(
            select(Volume).where(Volume.series_id == series.id, Volume.name == name)
        )
        volume = result.scalar_one_or_none()
        if volume is None:
            volume = Volume(series=series, name=name, start_year=volume_start_year)
            self.db.add(volume)
            await self.db.flush()
        elif volume.start_year is None and volume_start_year:
            volume.start_year = volume_start_year
        return volume

    async def _get_or_create_series(self, kind: ItemKind, title: str) -> Series:
        result = await self.db.execute(
            select(Series).where(Series.kind == kind, Series.title == title)
        )
        series = result.scalar_one_or_none()
        if series is None:
            series = Series(kind=kind, title=title, slug=self._slug(title))
            self.db.add(series)
            await self.db.flush()
        return series

    async def _add_provider_links(
        self,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        candidate_ids = provider_ids or {}
        if provider.value not in candidate_ids:
            candidate_ids = {provider.value: "", **candidate_ids}
        for provider_name, provider_id in candidate_ids.items():
            if not provider_id:
                continue
            try:
                provider_enum = ExternalProvider(provider_name)
            except ValueError:
                continue
            exists = await self.db.scalar(
                select(ExternalProviderId.id).where(
                    ExternalProviderId.provider == provider_enum,
                    ExternalProviderId.provider_item_id == provider_id,
                )
            )
            if exists:
                continue
            self.db.add(
                ExternalProviderId(
                    provider=provider_enum,
                    provider_item_id=provider_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
            )

    async def _link_publisher(self, item_id: UUID, publisher: str | None) -> None:
        if not publisher:
            return
        organization = await self._get_or_create_organization(publisher, "publisher")
        exists = await self.db.scalar(
            select(EntityOrganization.id).where(
                EntityOrganization.entity_type == "item",
                EntityOrganization.entity_id == item_id,
                EntityOrganization.organization_id == organization.id,
                EntityOrganization.role == "publisher",
            )
        )
        if exists:
            return
        self.db.add(
            EntityOrganization(
                entity_type="item",
                entity_id=item_id,
                organization_id=organization.id,
                role="publisher",
            )
        )

    async def _link_people(self, item_id: UUID, credits: list[NormalizedCredit]) -> None:
        for credit in credits:
            person = await self._get_or_create_person(credit.name)
            role = credit.role or "creator"
            exists = await self.db.scalar(
                select(EntityPerson.id).where(
                    EntityPerson.entity_type == "item",
                    EntityPerson.entity_id == item_id,
                    EntityPerson.person_id == person.id,
                    EntityPerson.role == role,
                )
            )
            if exists:
                continue
            self.db.add(
                EntityPerson(
                    entity_type="item",
                    entity_id=item_id,
                    person_id=person.id,
                    role=role,
                )
            )

    async def _link_tags(self, item_id: UUID, kind: str, credits: list[NormalizedCredit]) -> None:
        for credit in credits:
            tag = await self._get_or_create_tag(kind, credit.name)
            exists = await self.db.scalar(
                select(EntityTag.id).where(
                    EntityTag.entity_type == "item",
                    EntityTag.entity_id == item_id,
                    EntityTag.tag_id == tag.id,
                )
            )
            if exists:
                continue
            self.db.add(EntityTag(entity_type="item", entity_id=item_id, tag_id=tag.id))

    async def _get_or_create_organization(self, name: str, organization_type: str) -> Organization:
        result = await self.db.execute(
            select(Organization).where(
                Organization.name == name,
                Organization.type == organization_type,
            )
        )
        organization = result.scalar_one_or_none()
        if organization is None:
            organization = Organization(name=name, type=organization_type)
            self.db.add(organization)
            await self.db.flush()
        return organization

    async def _get_or_create_person(self, name: str) -> Person:
        result = await self.db.execute(select(Person).where(Person.name == name))
        person = result.scalar_one_or_none()
        if person is None:
            person = Person(name=name)
            self.db.add(person)
            await self.db.flush()
        return person

    async def _get_or_create_tag(self, kind: str, name: str) -> Tag:
        result = await self.db.execute(select(Tag).where(Tag.kind == kind, Tag.name == name))
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(kind=kind, name=name)
            self.db.add(tag)
            await self.db.flush()
        return tag

    def _sort_key(self, kind: ItemKind, title: str, item_number: str | None) -> str:
        media_type = media_type_for_kind(kind)
        padding = media_type.item_number_sort_padding if media_type else None
        normalized_number = item_number or ""
        if padding and normalized_number:
            normalized_number = normalized_number.zfill(padding)
        return f"{self._slug(title)}-{normalized_number}".strip("-")

    def _slug(self, value: str) -> str:
        return "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())

    async def _count(self, model: type) -> int:
        return int(await self.db.scalar(select(func.count()).select_from(model)) or 0)

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
        return int(
            await self.db.scalar(select(func.count()).select_from(Item).where(~has_cover)) or 0
        )

    async def _count_missing_provider_link_items(self) -> int:
        has_provider_link = exists().where(
            ExternalProviderId.entity_type == "item",
            ExternalProviderId.entity_id == Item.id,
        )
        return int(
            await self.db.scalar(select(func.count()).select_from(Item).where(~has_provider_link))
            or 0
        )

    async def _duplicate_group_count(self) -> int:
        return len(await self.duplicate_candidates(limit=200))

    async def _items_by_ids(self, item_ids: list[UUID]) -> list[Item]:
        unique_ids = list(dict.fromkeys(item_ids))
        result = await self.db.execute(
            select(Item)
            .options(
                selectinload(Item.volume).selectinload(Volume.series),
            )
            .where(Item.id.in_(unique_ids))
        )
        return list(result.scalars().unique())

    def _ensure_same_duplicate_group(self, items: list[Item]) -> None:
        if len(items) < 2:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_action_requires_multiple_items",
                detail="Duplicate action requires at least two items",
            )
        first = items[0]
        signature = (first.kind, first.title, first.item_number)
        if any((item.kind, item.title, item.item_number) != signature for item in items[1:]):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_group_mismatch",
                detail="Duplicate action items must belong to the same candidate group",
            )

    async def _duplicate_group_is_ignored(self, item_ids: list[UUID]) -> bool:
        if len(item_ids) < 2:
            return False
        token = self._duplicate_ignore_token(item_ids)
        result = await self.db.execute(select(Item.metadata_json).where(Item.id.in_(item_ids)))
        metadata_rows = list(result.scalars())
        if len(metadata_rows) != len(item_ids):
            return False
        return all(
            isinstance(metadata, dict) and metadata.get("admin_duplicate_ignore_token") == token
            for metadata in metadata_rows
        )

    async def _duplicate_conflict_flags(self, item_ids: list[UUID]) -> dict[str, bool]:
        provider_result = await self.db.execute(
            select(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
            .where(
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.entity_id.in_(item_ids),
            )
            .order_by(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
        )
        provider_ids_by_provider: dict[str, set[str]] = {}
        for provider, provider_item_id in provider_result.all():
            provider_ids_by_provider.setdefault(str(provider), set()).add(provider_item_id)
        has_provider_conflicts = any(len(ids) > 1 for ids in provider_ids_by_provider.values())

        cover_result = await self.db.execute(
            select(
                Variant.cover_image_url,
                Variant.thumbnail_image_url,
                Variant.cover_image_key,
                Variant.thumbnail_image_key,
            )
            .join(Edition, Variant.edition_id == Edition.id)
            .where(Edition.item_id.in_(item_ids))
        )
        cover_signatures = {
            tuple(value for value in row if value) for row in cover_result.all() if any(row)
        }
        return {
            "provider": has_provider_conflicts,
            "cover": len(cover_signatures) > 1,
        }

    def _duplicate_ignore_token(self, item_ids: list[UUID]) -> str:
        return "|".join(sorted(str(item_id) for item_id in item_ids))

    async def _move_item_children(self, source_item_id: UUID, target_item_id: UUID) -> None:
        await self.db.execute(
            update(Edition).where(Edition.item_id == source_item_id).values(item_id=target_item_id)
        )

        await self.db.execute(
            update(ExternalProviderId)
            .where(
                ExternalProviderId.entity_type == "item",
                ExternalProviderId.entity_id == source_item_id,
            )
            .values(entity_id=target_item_id)
        )

        await self._move_organization_links(source_item_id, target_item_id)
        await self._move_person_links(source_item_id, target_item_id)
        await self._move_tag_links(source_item_id, target_item_id)

        await self.db.execute(
            update(ImageAsset)
            .where(
                ImageAsset.entity_type == "item",
                ImageAsset.entity_id == source_item_id,
            )
            .values(entity_id=target_item_id)
        )

    async def _move_organization_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(EntityOrganization).where(
                EntityOrganization.entity_type == "item",
                EntityOrganization.entity_id == source_item_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityOrganization.id).where(
                    EntityOrganization.entity_type == "item",
                    EntityOrganization.entity_id == target_item_id,
                    EntityOrganization.organization_id == link.organization_id,
                    EntityOrganization.role == link.role,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_item_id

    async def _move_person_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(EntityPerson).where(
                EntityPerson.entity_type == "item",
                EntityPerson.entity_id == source_item_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityPerson.id).where(
                    EntityPerson.entity_type == "item",
                    EntityPerson.entity_id == target_item_id,
                    EntityPerson.person_id == link.person_id,
                    EntityPerson.role == link.role,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_item_id

    async def _move_tag_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(EntityTag).where(
                EntityTag.entity_type == "item",
                EntityTag.entity_id == source_item_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityTag.id).where(
                    EntityTag.entity_type == "item",
                    EntityTag.entity_id == target_item_id,
                    EntityTag.tag_id == link.tag_id,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_item_id

    async def _search_documents(self) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(Item).options(
                selectinload(Item.volume).selectinload(Volume.series),
                selectinload(Item.editions).selectinload(Edition.variants),
                selectinload(Item.editions).selectinload(Edition.releases),
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

    def _record_ingest_history(
        self,
        *,
        payload: ProviderIngestRequest,
        status: str,
        attempts: int,
        item_id: UUID | None = None,
        error: str | None = None,
    ) -> None:
        global _INGEST_HISTORY_SEQUENCE
        _INGEST_HISTORY_SEQUENCE += 1
        _INGEST_HISTORY.appendleft(
            ProviderIngestHistoryEntry(
                id=_INGEST_HISTORY_SEQUENCE,
                timestamp=datetime.now(UTC),
                provider=payload.provider,
                provider_item_id=payload.provider_item_id,
                status=status,
                attempts=attempts,
                item_id=item_id,
                error=error,
            )
        )

    async def _provider_ingest_success_count(self) -> int:
        job_count = await self._count_ingest_jobs("done")
        memory_count = sum(
            1 for entry in _INGEST_HISTORY if entry.status in {"created", "existing"}
        )
        return job_count + memory_count

    async def _provider_ingest_failure_count(self) -> int:
        job_count = await self._count_ingest_jobs("failed")
        memory_count = sum(1 for entry in _INGEST_HISTORY if entry.status == "failed")
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

    def _primary_edition_model(self, item: Item) -> Edition | None:
        editions = list(item.editions or [])
        return editions[0] if editions else None

    def _primary_variant_model(self, item: Item) -> Variant | None:
        for edition in item.editions or []:
            variants = list(edition.variants or [])
            primary = next((variant for variant in variants if variant.is_primary), None)
            if primary is not None:
                return primary
            if variants:
                return variants[0]
        return None

    def _record_admin_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            AdminAuditLog(
                action=action,
                actor_user_id=self.actor_user_id,
                actor_email=self.actor_email,
                entity_type=entity_type,
                entity_id=entity_id,
                details_json=self._audit_json_safe(details or {}),
            )
        )

    def _ingest_job_audit_details(self, job: ProviderIngestJob) -> dict[str, Any]:
        return {
            "provider": job.provider,
            "provider_item_id": job.provider_item_id,
            "status": job.status,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "item_id": job.item_id,
            "last_error": job.last_error,
        }

    def _audit_json_safe(self, value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime | date):
            return value.isoformat()
        if isinstance(value, PythonEnum):
            return value.value
        if isinstance(value, dict):
            return {str(key): self._audit_json_safe(item) for key, item in value.items()}
        if isinstance(value, list | tuple | set):
            return [self._audit_json_safe(item) for item in value]
        return value

    def _backoff_delay(self, attempts: int) -> timedelta:
        return timedelta(seconds=min(300, 5 * (2 ** max(0, attempts - 1))))

    def _is_retryable_ingest_error(self, error: Exception) -> bool:
        if isinstance(error, HTTPException):
            return error.status_code in {
                status.HTTP_429_TOO_MANY_REQUESTS,
                status.HTTP_502_BAD_GATEWAY,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_504_GATEWAY_TIMEOUT,
            }
        return False

    def _error_message(self, error: Exception) -> str:
        if isinstance(error, HTTPException):
            return str(error.detail)
        return str(error)
