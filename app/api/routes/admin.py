from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.admin import (
    AdminCatalogSummaryResponse,
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminMetadataCorrectionRequest,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    MetadataProposalAdminResponse,
    MetadataProposalSummaryResponse,
    ProviderIngestJobCreateRequest,
    ProviderIngestJobResponse,
    ProviderIngestJobRunResponse,
    ProviderIngestRequest,
    ProviderIngestRetryRequest,
    ProviderIngestResponse,
    ProviderIngestHistoryEntry,
    ProviderSearchRequest,
    ProviderStatusResponse,
)
from app.models.base import ExternalProvider, ItemKind
from app.schemas.metadata import ItemResponse
from app.services.admin import AdminMetadataService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/providers", response_model=list[ProviderStatusResponse])
async def providers(db: DbSession, user: CurrentAdmin) -> list[ProviderStatusResponse]:
    return await AdminMetadataService(db).provider_statuses()


@router.get("/catalog/summary", response_model=AdminCatalogSummaryResponse)
async def catalog_summary(db: DbSession, user: CurrentAdmin) -> AdminCatalogSummaryResponse:
    return await AdminMetadataService(db).catalog_summary()


@router.get("/catalog/items", response_model=list[ItemResponse])
async def catalog_items(
    db: DbSession,
    user: CurrentAdmin,
    q: str | None = Query(default=None, min_length=1, max_length=255),
    kind: ItemKind | None = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> list[ItemResponse]:
    return await AdminMetadataService(db).catalog_items(q, kind, limit)


@router.patch("/catalog/items/{kind}/{item_id}", response_model=ItemResponse)
async def catalog_item_update(
    kind: ItemKind,
    item_id: UUID,
    payload: AdminMetadataCorrectionRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> ItemResponse:
    return await AdminMetadataService(db).update_catalog_item(item_id, payload, kind)


@router.get("/search/status", response_model=AdminSearchStatusResponse)
async def search_status(db: DbSession, user: CurrentAdmin) -> AdminSearchStatusResponse:
    return await AdminMetadataService(db).search_status()


@router.post("/search/reindex", response_model=AdminSearchReindexResponse)
async def search_reindex(db: DbSession, user: CurrentAdmin) -> AdminSearchReindexResponse:
    return await AdminMetadataService(db).reindex_search()


@router.get("/search/history", response_model=list[AdminSearchHistoryEntry])
async def search_history(db: DbSession, user: CurrentAdmin) -> list[AdminSearchHistoryEntry]:
    return AdminMetadataService(db).search_history()


@router.get("/duplicates", response_model=list[AdminDuplicateCandidateResponse])
async def duplicate_candidates(
    db: DbSession,
    user: CurrentAdmin,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[AdminDuplicateCandidateResponse]:
    return await AdminMetadataService(db).duplicate_candidates(limit)


@router.post("/duplicates/ignore", response_model=AdminDuplicateActionResponse)
async def ignore_duplicate_candidate(
    payload: AdminDuplicateIgnoreRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> AdminDuplicateActionResponse:
    return await AdminMetadataService(db).ignore_duplicate_candidate(payload)


@router.post("/duplicates/merge", response_model=AdminDuplicateActionResponse)
async def merge_duplicate_candidate(
    payload: AdminDuplicateMergeRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> AdminDuplicateActionResponse:
    return await AdminMetadataService(db).merge_duplicate_candidate(payload)


@router.post("/providers/search")
async def provider_search(payload: ProviderSearchRequest, db: DbSession, user: CurrentAdmin):
    return await AdminMetadataService(db).provider_search(payload)


@router.post("/providers/ingest", response_model=ProviderIngestResponse, status_code=201)
async def provider_ingest(
    payload: ProviderIngestRequest, db: DbSession, user: CurrentAdmin
) -> ProviderIngestResponse:
    return await AdminMetadataService(db).ingest(payload)


@router.get("/providers/ingest/jobs", response_model=list[ProviderIngestJobResponse])
async def provider_ingest_jobs(
    db: DbSession,
    user: CurrentAdmin,
    status: str | None = Query(default=None, pattern="^(queued|running|done|failed)$"),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[ProviderIngestJobResponse]:
    return await AdminMetadataService(db).ingest_jobs(status, limit)


@router.post("/providers/ingest/jobs", response_model=ProviderIngestJobResponse, status_code=201)
async def provider_ingest_job_create(
    payload: ProviderIngestJobCreateRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestJobResponse:
    return await AdminMetadataService(db).create_ingest_job(payload)


@router.post("/providers/ingest/jobs/run-pending", response_model=ProviderIngestJobRunResponse)
async def provider_ingest_jobs_run_pending(
    db: DbSession,
    user: CurrentAdmin,
    limit: int = Query(default=5, ge=1, le=25),
) -> ProviderIngestJobRunResponse:
    return await AdminMetadataService(db).run_pending_ingest_jobs(limit)


@router.post("/providers/ingest/jobs/{job_id}/run", response_model=ProviderIngestJobResponse)
async def provider_ingest_job_run(
    job_id: UUID,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestJobResponse:
    return await AdminMetadataService(db).run_ingest_job(job_id)


@router.post("/providers/ingest/jobs/{job_id}/retry", response_model=ProviderIngestJobResponse)
async def provider_ingest_job_retry(
    job_id: UUID,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestJobResponse:
    return await AdminMetadataService(db).retry_ingest_job(job_id)


@router.get("/providers/ingest/history", response_model=list[ProviderIngestHistoryEntry])
async def provider_ingest_history(
    db: DbSession,
    user: CurrentAdmin,
) -> list[ProviderIngestHistoryEntry]:
    return AdminMetadataService(db).ingest_history()


@router.post("/providers/ingest/retry", response_model=ProviderIngestResponse)
async def provider_ingest_retry(
    payload: ProviderIngestRetryRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestResponse:
    return await AdminMetadataService(db).retry_ingest(payload)


@router.get("/metadata/proposals", response_model=list[MetadataProposalAdminResponse])
async def metadata_proposals(
    db: DbSession,
    user: CurrentAdmin,
    status: str = Query(default="pending", pattern="^(pending|approved|rejected)$"),
    provider: ExternalProvider | None = None,
) -> list[MetadataProposalAdminResponse]:
    return await AdminMetadataService(db).list_proposals(status, provider)


@router.get("/metadata/proposals/summary", response_model=MetadataProposalSummaryResponse)
async def metadata_proposals_summary(
    db: DbSession,
    user: CurrentAdmin,
) -> MetadataProposalSummaryResponse:
    return await AdminMetadataService(db).proposal_summary()


@router.post(
    "/metadata/proposals/{proposal_id}/approve",
    response_model=ProviderIngestResponse,
)
async def approve_metadata_proposal(
    proposal_id: UUID,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestResponse:
    return await AdminMetadataService(db).approve_proposal(proposal_id)


@router.post(
    "/metadata/proposals/{proposal_id}/approve-provider",
    response_model=ProviderIngestResponse,
)
async def approve_metadata_proposal_with_provider_item(
    proposal_id: UUID,
    payload: ProviderIngestRequest,
    db: DbSession,
    user: CurrentAdmin,
) -> ProviderIngestResponse:
    return await AdminMetadataService(db).approve_proposal_with_provider_item(
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
    return await AdminMetadataService(db).reject_proposal(proposal_id)
