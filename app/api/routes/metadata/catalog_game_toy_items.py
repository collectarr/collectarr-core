from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_game_toy_item import CatalogGameToyItemResponse
from app.schemas.metadata_shared import CatalogItemPage, catalog_item_page
from app.services.catalog_game_toy_items import CatalogGameToyItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/game-toys/items", response_model=CatalogItemPage[CatalogGameToyItemResponse])
async def search_game_toy_items(
    db: DbSession, q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0),
) -> CatalogItemPage[CatalogGameToyItemResponse]:
    rows = await CatalogGameToyItemService(db).search(
        query=q, barcode=barcode, limit=limit + 1, offset=offset)
    return catalog_item_page(rows, limit=limit, offset=offset)


@router.get("/metadata/game-toys/items/{item_id}", response_model=CatalogGameToyItemResponse)
async def get_game_toy_item(item_id: UUID, db: DbSession) -> CatalogGameToyItemResponse:
    return await CatalogGameToyItemService(db).get(item_id)
