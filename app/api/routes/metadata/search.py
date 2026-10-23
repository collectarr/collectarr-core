from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import TypeAdapter, ValidationError

from app.api.deps import DbSession
from app.catalog.release_scope import ReleasedCatalogKind
from app.core.errors import ApiHTTPException
from app.schemas.metadata_shared import CatalogSearchItemEnvelope, CatalogSearchPage
from app.services.facade import MetadataFacade as MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/search", response_model=CatalogSearchPage)
async def search(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    kind: ReleasedCatalogKind | None = None,
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
    offset: int = Query(default=0, ge=0),
    field_filters: str | None = Query(default=None, max_length=20000, description="JSON object mapping catalog-owned filter fields to selected string values"),
) -> CatalogSearchPage:
    try:
        filters = TypeAdapter(dict[str, list[str]]).validate_json(field_filters) if field_filters is not None else None
    except ValidationError as exc:
        raise ApiHTTPException(status_code=422, code="invalid_catalog_filters", detail="Search filters must be a JSON object of string lists") from exc
    return await MetadataService(db).search(
        query=q,
        field_filters=filters,
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
        offset=offset,
    )


@router.get("/barcode/{barcode}", response_model=CatalogSearchItemEnvelope)
async def lookup_barcode(
    barcode: str,
    db: DbSession,
    kind: ReleasedCatalogKind | None = None,
) -> CatalogSearchItemEnvelope:
    return await MetadataService(db).lookup_barcode(barcode, kind)
