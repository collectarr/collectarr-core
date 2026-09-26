import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import ItemKind
from app.models.user import User
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminCatalogSummaryResponse,
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminDuplicateQueueSummaryResponse,
    AdminDuplicateReviewEntryResponse,
    AdminDuplicateReviewRequest,
    AdminMetadataCorrectionRequest,
    AdminNormalizedMetadataDriftReportResponse,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
)
from app.search.client import SearchClient
from app.services.admin_domains import overview as overview_admin_module
from app.services.admin_domains.factory import build_admin_domain_services

logger = logging.getLogger(__name__)


class AdminMetadataService:
    """Source-neutral catalog and application administration operations."""

    def __init__(self, db: AsyncSession, actor: User | None = None) -> None:
        services = build_admin_domain_services(
            db=db,
            actor_user_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            logger=logger,
            search_client_cls=SearchClient,
        )
        self.catalog_admin = services.catalog_admin
        self.duplicates_admin = services.duplicates_admin
        self.overview_admin = services.overview_admin
        self.user_admin = services.user_admin
        self.image_cache_admin = services.image_cache_admin

    async def catalog_summary(self) -> AdminCatalogSummaryResponse:
        return await self.overview_admin.catalog_summary()

    async def normalized_metadata_drift_report(
        self, *, sample_limit: int = 100, scan_limit: int | None = None
    ) -> AdminNormalizedMetadataDriftReportResponse:
        return await self.catalog_admin.normalized_metadata_drift_report(
            sample_limit=sample_limit, scan_limit=scan_limit
        )

    async def search_status(self) -> AdminSearchStatusResponse:
        overview_admin_module.SearchClient = SearchClient
        return await self.overview_admin.search_status()

    async def reindex_search(self) -> AdminSearchReindexResponse:
        overview_admin_module.SearchClient = SearchClient
        return await self.overview_admin.reindex_search()

    def search_history(self) -> list[AdminSearchHistoryEntry]:
        return self.overview_admin.search_history()

    async def audit_logs(
        self,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        limit: int = 25,
    ) -> list[AdminAuditLogResponse]:
        return await self.overview_admin.audit_logs(action, entity_type, entity_id, limit)

    async def catalog_items(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        limit: int = 25,
        publisher: str | None = None,
        imprint: str | None = None,
        subtitle: str | None = None,
        series_group: str | None = None,
        country: str | None = None,
        language: str | None = None,
        age_rating: str | None = None,
        catalog_number: str | None = None,
        release_status: str | None = None,
    ) -> list[Any]:
        return await self.catalog_admin.catalog_items(
            query, kind, limit, publisher=publisher, imprint=imprint,
            subtitle=subtitle, series_group=series_group, country=country,
            language=language, age_rating=age_rating,
            catalog_number=catalog_number, release_status=release_status,
        )

    async def update_catalog_item(
        self, item_id: UUID, payload: AdminMetadataCorrectionRequest, kind: ItemKind | None = None
    ) -> Any:
        return await self.catalog_admin.update_catalog_item(item_id, payload, kind)

    async def duplicate_candidates(self, limit: int = 10) -> list[AdminDuplicateCandidateResponse]:
        return await self.duplicates_admin.duplicate_candidates(limit)

    async def duplicate_queue_summary(self) -> AdminDuplicateQueueSummaryResponse:
        return await self.duplicates_admin.duplicate_queue_summary()

    async def duplicate_review_history(self, limit: int = 25) -> list[AdminDuplicateReviewEntryResponse]:
        return await self.duplicates_admin.duplicate_review_history(limit)

    async def ignore_duplicate_candidate(
        self, payload: AdminDuplicateIgnoreRequest
    ) -> AdminDuplicateActionResponse:
        return await self.duplicates_admin.ignore_duplicate_candidate(payload)

    async def merge_duplicate_candidate(
        self, payload: AdminDuplicateMergeRequest
    ) -> AdminDuplicateActionResponse:
        return await self.duplicates_admin.merge_duplicate_candidate(payload)

    async def review_duplicate_candidate(
        self, payload: AdminDuplicateReviewRequest
    ) -> AdminDuplicateActionResponse:
        return await self.duplicates_admin.review_duplicate_candidate(payload)

    async def list_users(self) -> list:
        return await self.user_admin.list_users()

    async def get_user(self, user_id: UUID) -> Any:
        return await self.user_admin.get_user(user_id)

    async def update_user(self, user_id: UUID, payload: Any) -> Any:
        return await self.user_admin.update_user(user_id, payload)

    async def image_cache_stats(self) -> Any:
        return await self.image_cache_admin.image_cache_stats()

    async def purge_image_cache(self) -> Any:
        return await self.image_cache_admin.purge_image_cache()
