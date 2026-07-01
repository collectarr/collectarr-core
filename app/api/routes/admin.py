from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentAdmin, CurrentAdminReader, DbSession
from app.core.rate_limit import admin_provider_rate_limit
from app.models.base import ExternalProvider, ItemKind
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminCatalogSummaryResponse,
    AdminDeleteResponse,
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminDuplicateReviewRequest,
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
    ImageCachePurgeResponse,
    ImageCacheStatsResponse,
    MetadataProposalAdminResponse,
    MetadataProposalAdminUpdateRequest,
    MetadataProposalSummaryResponse,
    ProviderBatchHydrateRequest,
    ProviderBatchHydrateResponse,
    ProviderIngestHistoryEntry,
    ProviderIngestJobCreateRequest,
    ProviderIngestJobResponse,
    ProviderIngestJobRunResponse,
    ProviderIngestJobSummaryResponse,
    ProviderIngestRequest,
    ProviderIngestResponse,
    ProviderIngestRetryRequest,
    ProviderPayloadSnapshotPurgeResponse,
    ProviderPreviewResponse,
    ProviderSearchRequest,
    ProviderStatusListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.admin import AdminMetadataService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/metadata/mapping-rules",
    response_model=list[AdminReleaseMediaMappingRuleResponse],
)
async def metadata_mapping_rules(
    db: DbSession,
    _reader: CurrentAdminReader,
    provider: ExternalProvider | None = None,
    active: bool | None = Query(default=None),
) -> list[AdminReleaseMediaMappingRuleResponse]:
    return await AdminMetadataService(db).list_release_media_mapping_rules(provider, active)


@router.post(
    "/metadata/mapping-rules",
    response_model=AdminReleaseMediaMappingRuleResponse,
)
async def metadata_mapping_rule_create(
    payload: AdminReleaseMediaMappingRuleCreateRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> AdminReleaseMediaMappingRuleResponse:
    return await AdminMetadataService(db, user).create_release_media_mapping_rule(payload)


@router.patch(
    "/metadata/mapping-rules/{rule_id}",
    response_model=AdminReleaseMediaMappingRuleResponse,
)
async def metadata_mapping_rule_update(
    rule_id: UUID,
    payload: AdminReleaseMediaMappingRuleUpdateRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> AdminReleaseMediaMappingRuleResponse:
    return await AdminMetadataService(db, user).update_release_media_mapping_rule(rule_id, payload)


@router.delete(
    "/metadata/mapping-rules/{rule_id}",
    response_model=AdminDeleteResponse,
)
async def metadata_mapping_rule_delete(
    rule_id: UUID,
    db: DbSession,
    user: CurrentAdmin,
) -> AdminDeleteResponse:
    deleted = await AdminMetadataService(db, user).delete_release_media_mapping_rule(rule_id)
    return AdminDeleteResponse(deleted=deleted)


@router.post(
    "/providers/prefill/resolve",
    response_model=AdminProviderPrefillResolveResponse,
)
async def provider_prefill_resolve(
    payload: AdminProviderPrefillResolveRequest,
    db: DbSession,
    _reader: CurrentAdminReader,
) -> AdminProviderPrefillResolveResponse:
    return await AdminMetadataService(db).resolve_provider_prefill(payload)


@router.get("/providers", response_model=ProviderStatusListResponse)
async def providers(
    db: DbSession,
    _reader: CurrentAdminReader,
) -> ProviderStatusListResponse:
    service = AdminMetadataService(db)
    return ProviderStatusListResponse(
        providers=await service.provider_statuses(),
        cache_stats=await service.provider_cache_stats(),
    )


@router.get("/catalog/summary", response_model=AdminCatalogSummaryResponse)
async def catalog_summary(
    db: DbSession,
    _reader: CurrentAdminReader,
) -> AdminCatalogSummaryResponse:
    return await AdminMetadataService(db).catalog_summary()


@router.get(
    "/catalog/normalized-metadata-drift",
    response_model=AdminNormalizedMetadataDriftReportResponse,
)
async def catalog_normalized_metadata_drift(
    db: DbSession,
    _reader: CurrentAdminReader,
    sample_limit: int = Query(default=100, ge=1, le=500),
    scan_limit: int | None = Query(default=None, ge=100, le=100000),
) -> AdminNormalizedMetadataDriftReportResponse:
    return await AdminMetadataService(db).normalized_metadata_drift_report(
        sample_limit=sample_limit,
        scan_limit=scan_limit,
    )


@router.get("/catalog/items", response_model=list[dict[str, Any]])
async def catalog_items(
    db: DbSession,
    _reader: CurrentAdminReader,
    q: str | None = Query(default=None, min_length=1, max_length=255),
    kind: ItemKind | None = None,
    publisher: str | None = Query(default=None, min_length=1, max_length=255),
    imprint: str | None = Query(default=None, min_length=1, max_length=255),
    subtitle: str | None = Query(default=None, min_length=1, max_length=255),
    series_group: str | None = Query(default=None, min_length=1, max_length=255),
    country: str | None = Query(default=None, min_length=1, max_length=64),
    language: str | None = Query(default=None, min_length=1, max_length=32),
    age_rating: str | None = Query(default=None, min_length=1, max_length=64),
    catalog_number: str | None = Query(default=None, min_length=1, max_length=100),
    release_status: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[dict[str, Any]]:
    return await AdminMetadataService(db).catalog_items(
        q,
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


@router.patch("/catalog/items/{kind}/{item_id}", response_model=dict[str, Any])
async def catalog_item_update(
    kind: ItemKind,
    item_id: UUID,
    payload: AdminMetadataCorrectionRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> dict[str, Any]:
    return await AdminMetadataService(db, user).update_catalog_item(item_id, payload, kind)


@router.get("/search/status", response_model=AdminSearchStatusResponse)
async def search_status(
    db: DbSession,
    _reader: CurrentAdminReader,
) -> AdminSearchStatusResponse:
    return await AdminMetadataService(db).search_status()


@router.post("/search/reindex", response_model=AdminSearchReindexResponse)
async def search_reindex(db: DbSession, user: CurrentAdmin) -> AdminSearchReindexResponse:
    return await AdminMetadataService(db).reindex_search()


@router.get("/search/history", response_model=list[AdminSearchHistoryEntry])
async def search_history(
    db: DbSession,
    _reader: CurrentAdminReader,
) -> list[AdminSearchHistoryEntry]:
    return AdminMetadataService(db).search_history()


@router.get("/audit/logs", response_model=list[AdminAuditLogResponse])
async def audit_logs(
    db: DbSession,
    _reader: CurrentAdminReader,
    action: str | None = Query(default=None, min_length=1, max_length=100),
    entity_type: str | None = Query(default=None, min_length=1, max_length=64),
    entity_id: UUID | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[AdminAuditLogResponse]:
    return await AdminMetadataService(db).audit_logs(
        action,
        entity_type,
        entity_id,
        limit,
    )


@router.get("/duplicates", response_model=list[AdminDuplicateCandidateResponse])
async def duplicate_candidates(
    db: DbSession,
    _reader: CurrentAdminReader,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[AdminDuplicateCandidateResponse]:
    return await AdminMetadataService(db).duplicate_candidates(limit)


@router.post("/duplicates/ignore", response_model=AdminDuplicateActionResponse)
async def ignore_duplicate_candidate(
    payload: AdminDuplicateIgnoreRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> AdminDuplicateActionResponse:
    return await AdminMetadataService(db, user).ignore_duplicate_candidate(payload)


@router.post("/duplicates/merge", response_model=AdminDuplicateActionResponse)
async def merge_duplicate_candidate(
    payload: AdminDuplicateMergeRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> AdminDuplicateActionResponse:
    return await AdminMetadataService(db, user).merge_duplicate_candidate(payload)


@router.post("/duplicates/review", response_model=AdminDuplicateActionResponse)
async def review_duplicate_candidate(
    payload: AdminDuplicateReviewRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> AdminDuplicateActionResponse:
    return await AdminMetadataService(db, user).review_duplicate_candidate(payload)


@router.post("/providers/search", dependencies=[Depends(admin_provider_rate_limit)])
async def provider_search(
    payload: ProviderSearchRequest,
    db: DbSession,
    _reader: CurrentAdminReader,
):
    return await AdminMetadataService(db).provider_search(payload)


@router.post(
    "/providers/preview",
    response_model=ProviderPreviewResponse,
    dependencies=[Depends(admin_provider_rate_limit)],
)
async def provider_preview(
    payload: ProviderIngestRequest,
    db: DbSession,
    _reader: CurrentAdminReader,
) -> ProviderPreviewResponse:
    return await AdminMetadataService(db).preview(payload)


@router.post(
    "/providers/batch-hydrate",
    response_model=ProviderBatchHydrateResponse,
)
async def provider_batch_hydrate(
    payload: ProviderBatchHydrateRequest,
    db: DbSession,
    _reader: CurrentAdminReader,
) -> ProviderBatchHydrateResponse:
    return await AdminMetadataService(db).batch_hydrate(payload)


@router.post(
    "/providers/ingest",
    response_model=ProviderIngestResponse,
    status_code=201,
    dependencies=[Depends(admin_provider_rate_limit)],
)
async def provider_ingest(
    payload: ProviderIngestRequest, db: DbSession, user: CurrentAdmin
) -> ProviderIngestResponse:
    return await AdminMetadataService(db).ingest(payload)


@router.get("/providers/ingest/jobs", response_model=list[ProviderIngestJobResponse])
async def provider_ingest_jobs(
    db: DbSession,
    _reader: CurrentAdminReader,
    status: str | None = Query(default=None, pattern="^(queued|running|done|failed)$"),
    provider: ExternalProvider | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[ProviderIngestJobResponse]:
    return await AdminMetadataService(db).ingest_jobs(status, limit, provider, q)


@router.get(
    "/providers/ingest/jobs/summary",
    response_model=ProviderIngestJobSummaryResponse,
)
async def provider_ingest_jobs_summary(
    db: DbSession,
    _reader: CurrentAdminReader,
) -> ProviderIngestJobSummaryResponse:
    return await AdminMetadataService(db).ingest_job_summary()


@router.post(
    "/providers/ingest/jobs",
    response_model=ProviderIngestJobResponse,
    status_code=201,
    dependencies=[Depends(admin_provider_rate_limit)],
)
async def provider_ingest_job_create(
    payload: ProviderIngestJobCreateRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestJobResponse:
    return await AdminMetadataService(db, user).create_ingest_job(payload)


@router.post(
    "/providers/ingest/jobs/run-pending",
    response_model=ProviderIngestJobRunResponse,
    dependencies=[Depends(admin_provider_rate_limit)],
)
async def provider_ingest_jobs_run_pending(
    db: DbSession,
    user: CurrentAdmin,
    limit: int = Query(default=5, ge=1, le=25),
) -> ProviderIngestJobRunResponse:
    return await AdminMetadataService(db, user).run_pending_ingest_jobs(limit)


@router.post(
    "/providers/ingest/jobs/{job_id}/run",
    response_model=ProviderIngestJobResponse,
    dependencies=[Depends(admin_provider_rate_limit)],
)
async def provider_ingest_job_run(
    job_id: UUID,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestJobResponse:
    return await AdminMetadataService(db, user).run_ingest_job(job_id)


@router.post(
    "/providers/ingest/jobs/{job_id}/retry",
    response_model=ProviderIngestJobResponse,
    dependencies=[Depends(admin_provider_rate_limit)],
)
async def provider_ingest_job_retry(
    job_id: UUID,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestJobResponse:
    return await AdminMetadataService(db, user).retry_ingest_job(job_id)


@router.get("/providers/ingest/history", response_model=list[ProviderIngestHistoryEntry])
async def provider_ingest_history(
    db: DbSession,
    _reader: CurrentAdminReader,
) -> list[ProviderIngestHistoryEntry]:
    return AdminMetadataService(db).ingest_history()


@router.post(
    "/providers/ingest/retry",
    response_model=ProviderIngestResponse,
    dependencies=[Depends(admin_provider_rate_limit)],
)
async def provider_ingest_retry(
    payload: ProviderIngestRetryRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestResponse:
    return await AdminMetadataService(db, user).retry_ingest(payload)


@router.get("/metadata/proposals", response_model=list[MetadataProposalAdminResponse])
async def metadata_proposals(
    db: DbSession,
    _reader: CurrentAdminReader,
    status: str = Query(default="pending", pattern="^(pending|approved|rejected)$"),
    provider: ExternalProvider | None = None,
) -> list[MetadataProposalAdminResponse]:
    return await AdminMetadataService(db).list_proposals(status, provider)


@router.get("/metadata/proposals/summary", response_model=MetadataProposalSummaryResponse)
async def metadata_proposals_summary(
    db: DbSession,
    _reader: CurrentAdminReader,
) -> MetadataProposalSummaryResponse:
    return await AdminMetadataService(db).proposal_summary()


@router.patch(
    "/metadata/proposals/{proposal_id}",
    response_model=MetadataProposalAdminResponse,
)
async def update_metadata_proposal(
    proposal_id: UUID,
    payload: MetadataProposalAdminUpdateRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> MetadataProposalAdminResponse:
    return await AdminMetadataService(db, user).update_proposal(proposal_id, payload)


@router.post(
    "/metadata/proposals/{proposal_id}/approve",
    response_model=ProviderIngestResponse,
    dependencies=[Depends(admin_provider_rate_limit)],
)
async def approve_metadata_proposal(
    proposal_id: UUID,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestResponse:
    return await AdminMetadataService(db, user).approve_proposal(proposal_id)


@router.post(
    "/metadata/proposals/{proposal_id}/approve-provider",
    response_model=ProviderIngestResponse,
    dependencies=[Depends(admin_provider_rate_limit)],
)
async def approve_metadata_proposal_with_provider_item(
    proposal_id: UUID,
    payload: ProviderIngestRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestResponse:
    return await AdminMetadataService(db, user).approve_proposal_with_provider_item(
        proposal_id,
        payload,
    )


@router.post(
    "/metadata/proposals/{proposal_id}/reject",
    response_model=MetadataProposalAdminResponse,
)
async def reject_metadata_proposal(
    proposal_id: UUID,
    db: DbSession,
    user: CurrentAdmin,
) -> MetadataProposalAdminResponse:
    return await AdminMetadataService(db, user).reject_proposal(proposal_id)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserResponse])
async def list_users(db: DbSession, _user: CurrentAdmin) -> list[UserResponse]:
    return await AdminMetadataService(db).list_users()


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db: DbSession, _user: CurrentAdmin) -> UserResponse:
    return await AdminMetadataService(db).get_user(user_id)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> UserResponse:
    return await AdminMetadataService(db, user).update_user(user_id, payload)


@router.get("/image-cache/stats", response_model=ImageCacheStatsResponse)
async def image_cache_stats(
    db: DbSession,
    _reader: CurrentAdminReader,
) -> ImageCacheStatsResponse:
    return await AdminMetadataService(db).image_cache_stats()


@router.post("/image-cache/purge", response_model=ImageCachePurgeResponse)
async def purge_image_cache(
    db: DbSession,
    user: CurrentAdmin,
    provider: str | None = Query(None, description="Purge only entries for this provider"),
) -> ImageCachePurgeResponse:
    return await AdminMetadataService(db, user).purge_image_cache(provider=provider)


@router.post("/providers/snapshots/purge-expired", response_model=ProviderPayloadSnapshotPurgeResponse)
async def purge_expired_provider_snapshots(
    db: DbSession,
    user: CurrentAdmin,
    limit: int = Query(default=5000, ge=1, le=50000),
) -> ProviderPayloadSnapshotPurgeResponse:
    return await AdminMetadataService(db, user).purge_expired_provider_snapshots(limit=limit)
