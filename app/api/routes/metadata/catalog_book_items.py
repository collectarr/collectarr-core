from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_book_item import CatalogBookItemResponse
from app.services.catalog_book_items import CatalogBookItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/books/items", response_model=list[CatalogBookItemResponse])
async def search_book_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CatalogBookItemResponse]:
    return await CatalogBookItemService(db).search(
        query=q,
        barcode=barcode,
        limit=limit,
        offset=offset,
    )


@router.get("/metadata/books/items/{item_id}", response_model=CatalogBookItemResponse)
async def get_book_item(item_id: UUID, db: DbSession) -> CatalogBookItemResponse:
    return await CatalogBookItemService(db).get(item_id)
