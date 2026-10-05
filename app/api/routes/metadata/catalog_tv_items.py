"""Read flattened TV Catalog Items."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_tv_item import CatalogTvItemResponse
from app.schemas.metadata_shared import CatalogItemPage, catalog_item_page
from app.services.catalog_series_items import CatalogTvItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/tv/items", response_model=CatalogItemPage[CatalogTvItemResponse])
async def search_tv_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogItemPage[CatalogTvItemResponse]:
    rows = await CatalogTvItemService(db).search(
        query=q,
        barcode=barcode,
        limit=limit + 1,
        offset=offset,
    )
    return catalog_item_page(rows, limit=limit, offset=offset)


@router.get("/metadata/tv/items/{item_id}", response_model=CatalogTvItemResponse)
async def get_tv_item(item_id: UUID, db: DbSession) -> CatalogTvItemResponse:
    return await CatalogTvItemService(db).get(item_id)
