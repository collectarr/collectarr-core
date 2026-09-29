from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_game_item import CatalogGameItemResponse
from app.services.catalog_game_items import CatalogGameItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/games/items", response_model=list[CatalogGameItemResponse])
async def search_game_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CatalogGameItemResponse]:
    return await CatalogGameItemService(db).search(
        query=q,
        barcode=barcode,
        limit=limit,
        offset=offset,
    )


@router.get("/metadata/games/items/{item_id}", response_model=CatalogGameItemResponse)
async def get_game_item(item_id: UUID, db: DbSession) -> CatalogGameItemResponse:
    return await CatalogGameItemService(db).get(item_id)
