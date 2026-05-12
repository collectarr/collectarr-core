from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.admin import (
    MetadataProposalAdminResponse,
    ProviderIngestRequest,
    ProviderIngestResponse,
    ProviderSearchRequest,
    ProviderStatusResponse,
)
from app.services.admin import AdminMetadataService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/providers", response_model=list[ProviderStatusResponse])
async def providers(db: DbSession, user: CurrentAdmin) -> list[ProviderStatusResponse]:
    return await AdminMetadataService(db).provider_statuses()


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
) -> list[MetadataProposalAdminResponse]:
    return await AdminMetadataService(db).list_proposals(status)


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
    "/metadata/proposals/{proposal_id}/reject",
    response_model=MetadataProposalAdminResponse,
)
async def reject_metadata_proposal(
    proposal_id: UUID,
    db: DbSession,
    user: CurrentAdmin,
) -> MetadataProposalAdminResponse:
    return await AdminMetadataService(db).reject_proposal(proposal_id)
