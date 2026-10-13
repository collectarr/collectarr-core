from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_movie_item import CatalogMovieItemResponse
from app.schemas.metadata_shared import CatalogItemPage, catalog_item_page
from app.services.catalog_movie_items import CatalogMovieItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/movies/items", response_model=CatalogItemPage[CatalogMovieItemResponse])
async def search_movie_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogItemPage[CatalogMovieItemResponse]:
    rows = await CatalogMovieItemService(db).search(
        query=q,
        barcode=barcode,
        limit=limit + 1,
        offset=offset,
    )
    return catalog_item_page(rows, limit=limit, offset=offset)


@router.get("/metadata/movies/items/{item_id}", response_model=CatalogMovieItemResponse)
async def get_movie_item(item_id: UUID, db: DbSession) -> CatalogMovieItemResponse:
    return await CatalogMovieItemService(db).get(item_id)
