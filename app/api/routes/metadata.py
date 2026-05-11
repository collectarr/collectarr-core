from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.models.base import ExternalProvider, ItemKind
from app.schemas.metadata import (
    ItemResponse,
    MetadataProposalCreate,
    MetadataProposalResponse,
    ProviderSearchResultResponse,
    SearchResult,
)
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/search", response_model=list[SearchResult])
async def search(
    db: DbSession,
    q: str = Query(min_length=1),
    kind: ItemKind | None = None,
) -> list[SearchResult]:
    return await MetadataService(db).search(query=q, kind=kind)


@router.get("/barcode/{barcode}", response_model=SearchResult)
async def lookup_barcode(
    barcode: str,
    db: DbSession,
    kind: ItemKind | None = None,
) -> SearchResult:
    return await MetadataService(db).lookup_barcode(barcode, kind)


@router.get(
    "/metadata/providers/{provider}/search",
    response_model=list[ProviderSearchResultResponse],
)
async def provider_search(
    provider: ExternalProvider,
    db: DbSession,
    _user: CurrentUser,
    q: str = Query(min_length=1),
) -> list[ProviderSearchResultResponse]:
    return await MetadataService(db).search_provider(provider, q)


@router.post(
    "/metadata/proposals",
    response_model=MetadataProposalResponse,
    status_code=201,
)
async def create_metadata_proposal(
    payload: MetadataProposalCreate,
    db: DbSession,
    _user: CurrentUser,
) -> MetadataProposalResponse:
    return await MetadataService(db).create_proposal(payload)


@router.get("/comics/{item_id}", response_model=ItemResponse)
async def get_comic(item_id: UUID, db: DbSession) -> ItemResponse:
    return await MetadataService(db).get_item(item_id, ItemKind.comic)


@router.get("/games/{item_id}", response_model=ItemResponse)
async def get_game(item_id: UUID, db: DbSession) -> ItemResponse:
    return await MetadataService(db).get_item(item_id, ItemKind.game)


@router.get("/blu-ray/{item_id}", response_model=ItemResponse)
async def get_bluray(item_id: UUID, db: DbSession) -> ItemResponse:
    return await MetadataService(db).get_item(item_id, ItemKind.bluray)
