"""Read flattened Comic Catalog Items."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_comic_item import CatalogComicItemResponse, CatalogComicSeriesResponse
from app.schemas.metadata_shared import (
    CatalogItemPage,
    CatalogSearchItemEnvelope,
    catalog_item_page,
)
from app.services.catalog_comic_items import CatalogComicItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/comics/items", response_model=CatalogItemPage[CatalogComicItemResponse])
async def search_comic_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogItemPage[CatalogComicItemResponse]:
    rows = await CatalogComicItemService(db).search(
        query=q,
        barcode=barcode,
        limit=limit + 1,
        offset=offset,
    )
    return catalog_item_page(rows, limit=limit, offset=offset)


@router.get("/metadata/comics/series", response_model=list[CatalogComicSeriesResponse])
async def search_comic_series(
    db: DbSession,
    q: str = Query(min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[CatalogComicSeriesResponse]:
    return await CatalogComicItemService(db).search_series(query=q, limit=limit)


@router.get(
    "/metadata/comics/series/issues",
    response_model=list[CatalogSearchItemEnvelope],
    description="Every issue of one series. An omitted publisher or volume start year selects the series without one.",
)
async def get_comic_series_issues(
    db: DbSession,
    series_title: str = Query(min_length=1),
    publisher: str | None = Query(default=None, min_length=1),
    volume_start_year: int | None = Query(default=None, ge=1800, le=2200),
) -> list[CatalogSearchItemEnvelope]:
    return await CatalogComicItemService(db).series_issues(
        series_title=series_title,
        publisher=publisher,
        volume_start_year=volume_start_year,
    )


@router.get("/metadata/comics/items/{item_id}", response_model=CatalogComicItemResponse)
async def get_comic_item(item_id: UUID, db: DbSession) -> CatalogComicItemResponse:
    return await CatalogComicItemService(db).get(item_id)
