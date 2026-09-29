"""Read flattened Anime Catalog Items."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_anime_item import CatalogAnimeItemResponse
from app.services.catalog_series_items import CatalogAnimeItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/anime/items", response_model=list[CatalogAnimeItemResponse])
async def search_anime_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CatalogAnimeItemResponse]:
    return await CatalogAnimeItemService(db).search(
        query=q,
        barcode=barcode,
        limit=limit,
        offset=offset,
    )


@router.get("/metadata/anime/items/{item_id}", response_model=CatalogAnimeItemResponse)
async def get_anime_item(item_id: UUID, db: DbSession) -> CatalogAnimeItemResponse:
    return await CatalogAnimeItemService(db).get(item_id)
