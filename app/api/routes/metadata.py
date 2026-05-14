from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.catalog.media_types import MediaTypeConfig, media_type_for_route, media_types
from app.catalog.physical_formats import PhysicalFormatConfig
from app.core.errors import ApiHTTPException
from app.models.base import ExternalProvider, ItemKind
from app.schemas.metadata import (
    ItemResponse,
    MediaTypeResponse,
    MetadataProposalCreate,
    MetadataProposalResponse,
    PhysicalFormatResponse,
    ProviderSearchResultResponse,
    SearchResult,
)
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/media-types", response_model=list[MediaTypeResponse])
async def media_type_catalog() -> list[MediaTypeResponse]:
    return [_media_type_response(config) for config in media_types]


@router.get("/search", response_model=list[SearchResult])
async def search(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    kind: ItemKind | None = None,
    series: str | None = Query(default=None, min_length=1),
    issue_number: str | None = Query(default=None, min_length=1),
    publisher: str | None = Query(default=None, min_length=1),
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


@router.get(
    "/metadata/providers/{provider}/search",
    response_model=list[ProviderSearchResultResponse],
)
async def provider_search(
    provider: ExternalProvider,
    db: DbSession,
    _user: CurrentUser,
    q: str = Query(min_length=1),
    kind: ItemKind | None = None,
) -> list[ProviderSearchResultResponse]:
    return await MetadataService(db).search_provider(provider, q, kind)


@router.post(
    "/metadata/proposals",
    response_model=MetadataProposalResponse,
    status_code=201,
)
async def create_metadata_proposal(
    payload: MetadataProposalCreate,
    db: DbSession,
    _user: CurrentUser,
) -> MetadataProposalResponse:
    return await MetadataService(db).create_proposal(payload)


@router.get("/metadata/{media_type}/{item_id}", response_model=ItemResponse)
async def get_metadata_item(media_type: str, item_id: UUID, db: DbSession) -> ItemResponse:
    return await _get_metadata_item(media_type, item_id, db)


@router.get("/{media_type}/{item_id}", response_model=ItemResponse)
async def get_metadata_item_alias(media_type: str, item_id: UUID, db: DbSession) -> ItemResponse:
    return await _get_metadata_item(media_type, item_id, db)


async def _get_metadata_item(media_type: str, item_id: UUID, db: DbSession) -> ItemResponse:
    media_config = media_type_for_route(media_type)
    if media_config is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="media_type_not_found",
            detail=f"Unknown media type '{media_type}'",
        )
    return await MetadataService(db).get_item(item_id, media_config.kind)


def _media_type_response(config: MediaTypeConfig) -> MediaTypeResponse:
    return MediaTypeResponse(
        kind=config.kind,
        singular_label=config.singular_label,
        plural_label=config.plural_label,
        route_segments=list(config.route_segments),
        default_provider=config.default_provider,
        providers=list(config.providers),
        is_top_level=config.is_top_level,
        legacy_of=config.legacy_of,
        physical_formats=[_physical_format_response(row) for row in config.physical_formats],
    )


def _physical_format_response(config: PhysicalFormatConfig) -> PhysicalFormatResponse:
    return PhysicalFormatResponse(
        id=config.id,
        label=config.label,
        media_family=config.media_family,
        variant_type=config.variant_type,
        aliases=list(config.aliases),
    )
