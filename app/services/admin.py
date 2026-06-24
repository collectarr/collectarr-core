import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import ExternalProvider, ItemKind
from app.models.user import User
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminBundleReleaseCorrectionRequest,
    AdminCatalogSummaryResponse,
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminMetadataCorrectionRequest,
    AdminNormalizedMetadataDriftReportResponse,
    AdminProviderPrefillResolveRequest,
    AdminProviderPrefillResolveResponse,
    AdminReleaseMediaMappingRuleCreateRequest,
    AdminReleaseMediaMappingRuleResponse,
    AdminReleaseMediaMappingRuleUpdateRequest,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    AdminSeriesTagsUpdateRequest,
    MetadataProposalAdminResponse,
    MetadataProposalAdminUpdateRequest,
    MetadataProposalSummaryResponse,
    ProviderBatchHydrateRequest,
    ProviderBatchHydrateResponse,
    ProviderCacheSummaryResponse,
    ProviderIngestHistoryEntry,
    ProviderIngestJobCreateRequest,
    ProviderIngestJobResponse,
    ProviderIngestJobRunResponse,
    ProviderIngestJobSummaryResponse,
    ProviderIngestRequest,
    ProviderIngestResponse,
    ProviderIngestRetryRequest,
    ProviderPreviewResponse,
    ProviderSearchRequest,
    ProviderStatusResponse,
)
from app.schemas.metadata import (
    BundleReleaseDetailResponse,
    SeriesResponse,
)
from app.search.client import SearchClient
from app.services.admin_domains import overview as overview_admin_module
from app.services.admin_domains.factory import build_admin_domain_services

logger = logging.getLogger(__name__)


class AdminMetadataService:
    def __init__(self, db: AsyncSession, actor: User | None = None) -> None:
        services = build_admin_domain_services(
            db=db,
            actor_user_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            logger=logger,
            search_client_cls=SearchClient,
        )
        self.provider_ingest_admin = services.provider_ingest_admin
        self.rules_admin = services.rules_admin
        self.catalog_admin = services.catalog_admin
        self.duplicates_admin = services.duplicates_admin
        self.overview_admin = services.overview_admin
        self.user_admin = services.user_admin
        self.image_cache_admin = services.image_cache_admin
        self.providers = self.provider_ingest_admin.providers

    async def provider_statuses(self) -> list[ProviderStatusResponse]:
        return await self.overview_admin.provider_statuses()

    async def list_release_media_mapping_rules(
        self,
        provider_filter: ExternalProvider | None = None,
        active_filter: bool | None = None,
    ) -> list[AdminReleaseMediaMappingRuleResponse]:
        return await self.rules_admin.list_release_media_mapping_rules(provider_filter, active_filter)

    async def create_release_media_mapping_rule(
        self,
        payload: AdminReleaseMediaMappingRuleCreateRequest,
    ) -> AdminReleaseMediaMappingRuleResponse:
        return await self.rules_admin.create_release_media_mapping_rule(payload)

    async def update_release_media_mapping_rule(
        self,
        rule_id: UUID,
        payload: AdminReleaseMediaMappingRuleUpdateRequest,
    ) -> AdminReleaseMediaMappingRuleResponse:
        return await self.rules_admin.update_release_media_mapping_rule(rule_id, payload)

    async def delete_release_media_mapping_rule(self, rule_id: UUID) -> bool:
        return await self.rules_admin.delete_release_media_mapping_rule(rule_id)

    async def resolve_provider_prefill(
        self,
        payload: AdminProviderPrefillResolveRequest,
    ) -> AdminProviderPrefillResolveResponse:
        return await self.rules_admin.resolve_provider_prefill(payload)

    async def provider_cache_stats(self) -> ProviderCacheSummaryResponse:
        return await self.overview_admin.provider_cache_stats()

    async def catalog_summary(self) -> AdminCatalogSummaryResponse:
        return await self.overview_admin.catalog_summary()

    async def normalized_metadata_drift_report(
        self,
        *,
        sample_limit: int = 100,
        scan_limit: int | None = None,
    ) -> AdminNormalizedMetadataDriftReportResponse:
        return await self.catalog_admin.normalized_metadata_drift_report(
            sample_limit=sample_limit,
            scan_limit=scan_limit,
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
            query,
            kind,
            limit,
            publisher=publisher,
            imprint=imprint,
            subtitle=subtitle,
            series_group=series_group,
            country=country,
            language=language,
            age_rating=age_rating,
            catalog_number=catalog_number,
            release_status=release_status,
        )

    async def update_catalog_item(
        self,
        item_id: UUID,
        payload: AdminMetadataCorrectionRequest,
        kind: ItemKind | None = None,
    ) -> Any:
        return await self.catalog_admin.update_catalog_item(item_id, payload, kind)

    async def update_series_tags(
        self,
        series_id: UUID,
        payload: AdminSeriesTagsUpdateRequest,
    ) -> SeriesResponse:
        return await self.catalog_admin.update_series_tags(series_id, payload)

    async def update_bundle_release(
        self,
        bundle_release_id: UUID,
        payload: AdminBundleReleaseCorrectionRequest,
    ) -> BundleReleaseDetailResponse:
        return await self.catalog_admin.update_bundle_release(bundle_release_id, payload)

    

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
        return await self.duplicates_admin.duplicate_candidates(limit)

    async def ignore_duplicate_candidate(
        self, payload: AdminDuplicateIgnoreRequest
    ) -> AdminDuplicateActionResponse:
        return await self.duplicates_admin.ignore_duplicate_candidate(payload)

    async def merge_duplicate_candidate(
        self, payload: AdminDuplicateMergeRequest
    ) -> AdminDuplicateActionResponse:
        return await self.duplicates_admin.merge_duplicate_candidate(payload)

    async def provider_search(self, payload: ProviderSearchRequest) -> list[dict[str, Any]]:
        return await self.provider_ingest_admin.provider_search(payload)

    async def proposal_summary(self) -> MetadataProposalSummaryResponse:
        return await self.provider_ingest_admin.proposal_summary()

    async def list_proposals(
        self, status_filter: str = "pending", provider_filter: ExternalProvider | None = None
    ) -> list[MetadataProposalAdminResponse]:
        return await self.provider_ingest_admin.list_proposals(status_filter, provider_filter)

    async def update_proposal(
        self, proposal_id: UUID, payload: MetadataProposalAdminUpdateRequest
    ) -> MetadataProposalAdminResponse:
        return await self.provider_ingest_admin.update_proposal(proposal_id, payload)

    async def approve_proposal(self, proposal_id: UUID) -> ProviderIngestResponse:
        return await self.provider_ingest_admin.approve_proposal(proposal_id)

    async def approve_proposal_with_provider_item(
        self,
        proposal_id: UUID,
        payload: ProviderIngestRequest,
    ) -> ProviderIngestResponse:
        return await self.provider_ingest_admin.approve_proposal_with_provider_item(proposal_id, payload)

    async def reject_proposal(self, proposal_id: UUID) -> MetadataProposalAdminResponse:
        return await self.provider_ingest_admin.reject_proposal(proposal_id)

    async def create_ingest_job(
        self,
        payload: ProviderIngestJobCreateRequest,
    ) -> ProviderIngestJobResponse:
        return await self.provider_ingest_admin.create_ingest_job(payload)

    async def ingest_jobs(
        self,
        status_filter: str | None = None,
        limit: int = 25,
        provider_filter: ExternalProvider | None = None,
        query: str | None = None,
    ) -> list[ProviderIngestJobResponse]:
        return await self.provider_ingest_admin.ingest_jobs(status_filter, limit, provider_filter, query)

    async def ingest_job_summary(self) -> ProviderIngestJobSummaryResponse:
        return await self.provider_ingest_admin.ingest_job_summary()

    async def run_ingest_job(self, job_id: UUID) -> ProviderIngestJobResponse:
        return await self.provider_ingest_admin.run_ingest_job(job_id)

    async def retry_ingest_job(self, job_id: UUID) -> ProviderIngestJobResponse:
        return await self.provider_ingest_admin.retry_ingest_job(job_id)

    async def run_pending_ingest_jobs(self, limit: int = 5) -> ProviderIngestJobRunResponse:
        return await self.provider_ingest_admin.run_pending_ingest_jobs(limit)

    async def recover_stale_ingest_jobs(self) -> int:
        return await self.provider_ingest_admin.recover_stale_ingest_jobs()

    def ingest_history(self) -> list[ProviderIngestHistoryEntry]:
        return self.provider_ingest_admin.ingest_history()

    async def refresh_stale_items(self, limit: int = 10) -> int:
        return await self.provider_ingest_admin.refresh_stale_items(limit)

    async def retry_ingest(self, payload: ProviderIngestRetryRequest) -> ProviderIngestResponse:
        return await self.provider_ingest_admin.retry_ingest(payload)

    async def preview(self, payload: ProviderIngestRequest) -> ProviderPreviewResponse:
        return await self.provider_ingest_admin.preview(payload)

    async def batch_hydrate(
        self,
        payload: ProviderBatchHydrateRequest,
    ) -> ProviderBatchHydrateResponse:
        return await self.provider_ingest_admin.batch_hydrate(payload)

    async def ingest(self, payload: ProviderIngestRequest) -> ProviderIngestResponse:
        return await self.provider_ingest_admin.ingest(payload)

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    async def list_users(self) -> list:
        return await self.user_admin.list_users()

    async def get_user(self, user_id: UUID) -> Any:
        return await self.user_admin.get_user(user_id)

    async def update_user(self, user_id: UUID, payload: Any) -> Any:
        return await self.user_admin.update_user(user_id, payload)

    async def image_cache_stats(self) -> Any:
        return await self.image_cache_admin.image_cache_stats()

    async def purge_image_cache(self, provider: str | None = None) -> Any:
        return await self.image_cache_admin.purge_image_cache(provider=provider)
