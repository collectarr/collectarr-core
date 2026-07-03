from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession
from app.core.rate_limit import provider_search_rate_limit
from app.models.base import ExternalProvider, ItemKind
from app.schemas import ProviderSearchResultResponse, SeasonResponse
from app.schemas.admin import (
    ProviderBatchHydrateRequest,
    ProviderBatchHydrateResponse,
    ProviderPreviewResponse,
)
from app.schemas.admin import ProviderIngestRequest as ProviderPreviewRequest
from app.services.admin import AdminMetadataService
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get(
    "/metadata/providers/search",
    response_model=list[ProviderSearchResultResponse],
    dependencies=[Depends(provider_search_rate_limit)],
)
async def default_provider_search(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    kind: ItemKind = Query(...),
    series: str | None = Query(default=None, min_length=1, max_length=255),
    issue_number: str | None = Query(default=None, min_length=1, max_length=64),
    year: int | None = Query(default=None, ge=1800, le=2200),
) -> list[ProviderSearchResultResponse]:
    return await MetadataService(db).search_default_provider(
        q,
        kind,
        series=series,
        issue_number=issue_number,
        year=year,
    )


@router.get(
    "/metadata/providers/{provider}/search",
    response_model=list[ProviderSearchResultResponse],
    dependencies=[Depends(provider_search_rate_limit)],
)
async def provider_search(
    provider: ExternalProvider,
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    kind: ItemKind | None = None,
    series: str | None = Query(default=None, min_length=1),
    issue_number: str | None = Query(default=None, min_length=1),
    year: int | None = Query(default=None, ge=1800, le=2200),
) -> list[ProviderSearchResultResponse]:
    return await MetadataService(db).search_provider(
        provider,
        q,
        kind,
        series=series,
        issue_number=issue_number,
        year=year,
    )


@router.post(
    "/metadata/providers/preview",
    response_model=ProviderPreviewResponse,
    dependencies=[Depends(provider_search_rate_limit)],
)
async def provider_preview(
    payload: ProviderPreviewRequest,
    db: DbSession,
) -> ProviderPreviewResponse:
    return await AdminMetadataService(db).preview(payload)


@router.get(
    "/metadata/providers/{provider}/seasons/{provider_item_id:path}",
    response_model=list[SeasonResponse],
)
async def get_provider_seasons(
    provider: ExternalProvider,
    provider_item_id: str,
    db: DbSession,
) -> list[SeasonResponse]:
    return await MetadataService(db).get_provider_seasons(provider, provider_item_id)


@router.get(
    "/metadata/providers/{provider}/volumes/{provider_item_id:path}",
    response_model=list[SeasonResponse],
)
async def get_provider_volumes(
    provider: ExternalProvider,
    provider_item_id: str,
    db: DbSession,
) -> list[SeasonResponse]:
    return await MetadataService(db).get_provider_volumes(provider, provider_item_id)


@router.post("/providers/batch-hydrate", response_model=ProviderBatchHydrateResponse)
async def provider_batch_hydrate(
    payload: ProviderBatchHydrateRequest,
    db: DbSession,
) -> ProviderBatchHydrateResponse:
    return await AdminMetadataService(db).batch_hydrate(payload)
