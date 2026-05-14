from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.admin import (
    AdminCatalogSummaryResponse,
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    MetadataProposalAdminResponse,
    MetadataProposalSummaryResponse,
    ProviderIngestRequest,
    ProviderIngestResponse,
    ProviderSearchRequest,
    ProviderStatusResponse,
)
from app.models.base import ExternalProvider
from app.services.admin import AdminMetadataService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/providers", response_model=list[ProviderStatusResponse])
async def providers(db: DbSession, user: CurrentAdmin) -> list[ProviderStatusResponse]:
    return await AdminMetadataService(db).provider_statuses()


@router.get("/catalog/summary", response_model=AdminCatalogSummaryResponse)
async def catalog_summary(db: DbSession, user: CurrentAdmin) -> AdminCatalogSummaryResponse:
    return await AdminMetadataService(db).catalog_summary()


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
