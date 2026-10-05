from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_boardgame_item import CatalogBoardGameItemResponse
from app.schemas.metadata_shared import CatalogItemPage, catalog_item_page
from app.services.catalog_boardgame_items import CatalogBoardGameItemService

router = APIRouter(tags=["metadata"])


@router.get(
    "/metadata/boardgames/items",
    response_model=CatalogItemPage[CatalogBoardGameItemResponse],
)
async def search_boardgame_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogItemPage[CatalogBoardGameItemResponse]:
    rows = await CatalogBoardGameItemService(db).search(
        query=q,
        barcode=barcode,
        limit=limit + 1,
        offset=offset,
    )
    return catalog_item_page(rows, limit=limit, offset=offset)


@router.get(
    "/metadata/boardgames/items/{item_id}",
    response_model=CatalogBoardGameItemResponse,
)
async def get_boardgame_item(
    item_id: UUID,
    db: DbSession,
) -> CatalogBoardGameItemResponse:
    return await CatalogBoardGameItemService(db).get(item_id)
