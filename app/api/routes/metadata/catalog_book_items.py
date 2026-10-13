from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_book_item import CatalogBookItemResponse
from app.schemas.metadata_shared import CatalogItemPage, catalog_item_page
from app.services.catalog_book_items import CatalogBookItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/books/items", response_model=CatalogItemPage[CatalogBookItemResponse])
async def search_book_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogItemPage[CatalogBookItemResponse]:
    rows = await CatalogBookItemService(db).search(
        query=q,
        barcode=barcode,
        limit=limit + 1,
        offset=offset,
    )
    return catalog_item_page(rows, limit=limit, offset=offset)


@router.get("/metadata/books/items/{item_id}", response_model=CatalogBookItemResponse)
async def get_book_item(item_id: UUID, db: DbSession) -> CatalogBookItemResponse:
    return await CatalogBookItemService(db).get(item_id)
