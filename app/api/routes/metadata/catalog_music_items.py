from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.catalog_music_item import (
    CatalogMusicItemResponse,
    CatalogMusicItemSearchPage,
)
from app.services.catalog_music_items import CatalogMusicItemService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/music/items", response_model=CatalogMusicItemSearchPage)
async def search_music_items(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    barcode: str | None = Query(default=None, min_length=1),
    artist: str | None = Query(default=None, min_length=1),
    label: str | None = Query(default=None, min_length=1),
    subtitle: str | None = Query(default=None, min_length=1),
    country: str | None = Query(default=None, min_length=1),
    catalog_number: str | None = Query(default=None, min_length=1),
    year: int | None = Query(default=None, ge=1800, le=2200),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogMusicItemSearchPage:
    return await CatalogMusicItemService(db).search(
        query=q,
        barcode=barcode,
        artist=artist,
        label=label,
        subtitle=subtitle,
        country=country,
        catalog_number=catalog_number,
        year=year,
        limit=limit,
        offset=offset,
    )


@router.get("/metadata/music/items/{item_id}", response_model=CatalogMusicItemResponse)
async def get_music_item(item_id: UUID, db: DbSession) -> CatalogMusicItemResponse:
    return await CatalogMusicItemService(db).get(item_id)
