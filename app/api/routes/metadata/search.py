from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/search", response_model=list[SearchResult])
async def search(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    kind: ItemKind | None = None,
    series: str | None = Query(default=None, min_length=1),
    issue_number: str | None = Query(default=None, min_length=1),
    publisher: str | None = Query(default=None, min_length=1),
    imprint: str | None = Query(default=None, min_length=1),
    subtitle: str | None = Query(default=None, min_length=1),
    series_group: str | None = Query(default=None, min_length=1),
    language: str | None = Query(default=None, min_length=1),
    country: str | None = Query(default=None, min_length=1),
    age_rating: str | None = Query(default=None, min_length=1),
    catalog_number: str | None = Query(default=None, min_length=1),
    release_status: str | None = Query(default=None, min_length=1),
    year: int | None = Query(default=None, ge=1800, le=2200),
    barcode: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[SearchResult]:
    return await MetadataService(db).search(
        query=q,
        kind=kind,
        series=series,
        issue_number=issue_number,
        publisher=publisher,
        imprint=imprint,
        subtitle=subtitle,
        series_group=series_group,
        language=language,
        country=country,
        age_rating=age_rating,
        catalog_number=catalog_number,
        release_status=release_status,
        year=year,
        barcode=barcode,
        limit=limit,
    )


@router.get("/barcode/{barcode}", response_model=SearchResult)
async def lookup_barcode(
    barcode: str,
    db: DbSession,
    kind: ItemKind | None = None,
) -> SearchResult:
    return await MetadataService(db).lookup_barcode(barcode, kind)

