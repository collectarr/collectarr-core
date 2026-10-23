from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_game_hardware_item import CatalogGameHardwareItemResponse
from app.schemas.metadata_shared import CatalogItemPage, catalog_item_page
from app.services.catalog_game_hardware_items import CatalogGameHardwareItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/game-hardware/items", response_model=CatalogItemPage[CatalogGameHardwareItemResponse])
async def search_game_hardware_items(
    db: DbSession, q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0),
) -> CatalogItemPage[CatalogGameHardwareItemResponse]:
    rows = await CatalogGameHardwareItemService(db).search(
        query=q, barcode=barcode, limit=limit + 1, offset=offset)
    return catalog_item_page(rows, limit=limit, offset=offset)


@router.get("/metadata/game-hardware/items/{item_id}", response_model=CatalogGameHardwareItemResponse)
async def get_game_hardware_item(item_id: UUID, db: DbSession) -> CatalogGameHardwareItemResponse:
    return await CatalogGameHardwareItemService(db).get(item_id)
