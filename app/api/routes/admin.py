from fastapi import APIRouter

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.admin import (
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
