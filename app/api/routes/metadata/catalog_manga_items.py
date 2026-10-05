from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_manga_item import CatalogMangaItemResponse
from app.schemas.metadata_shared import CatalogItemPage, catalog_item_page
from app.services.catalog_manga_items import CatalogMangaItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/manga/items", response_model=CatalogItemPage[CatalogMangaItemResponse])
async def search_manga_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogItemPage[CatalogMangaItemResponse]:
    rows = await CatalogMangaItemService(db).search(
        query=q,
        barcode=barcode,
        limit=limit + 1,
        offset=offset,
    )
    return catalog_item_page(rows, limit=limit, offset=offset)


@router.get("/metadata/manga/items/{item_id}", response_model=CatalogMangaItemResponse)
async def get_manga_item(item_id: UUID, db: DbSession) -> CatalogMangaItemResponse:
    return await CatalogMangaItemService(db).get(item_id)
