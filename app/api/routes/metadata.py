from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, DbSession
from app.catalog.media_types import (
    MediaTypeConfig,
    media_type_for_route,
    top_level_media_types,
)
from app.catalog.metadata_fields import (
    METADATA_FIELDS,
    fields_for_kind,
)
from app.catalog.physical_formats import PhysicalFormatConfig
from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.core.rate_limit import provider_search_rate_limit
from app.metadata_normalized import (
    NORMALIZED_SCHEMA_VERSION,
    normalized_metadata_manifest,
)
from app.models.base import ExternalProvider, ItemKind
from app.providers.gcd import GCDCoverFallback, GCDCoverImage, GCDProvider
from app.providers.mangadex import MangaDexProvider
from app.schemas import (
    AnimeEpisodeV1Response,
    AnimeSeriesV1Response,
    BookEditionV1Response,
    BookWorkV1Response,
    CharacterAppearanceResponse,
    CharacterFacetResponse,
    CharacterResponse,
    ComicIssueV1Response,
    ComicWorkV1Response,
    CreatorCreditResponse,
    CreatorFacetResponse,
    CreatorResponse,
    FacetItemIdsRequest,
    MangaChapterV1Response,
    MangaWorkV1Response,
    MediaCatalogResponse,
    MediaTypeResponse,
    MetadataFieldSchemaResponse,
    MetadataFieldSpecResponse,
    MetadataNormalizedManifestResponse,
    MetadataProposalCreate,
    MetadataProposalResponse,
    MovieReleaseV1Response,
    MovieWorkV1Response,
    PhysicalFormatResponse,
    ProviderSearchResultResponse,
    SeasonResponse,
    StoryArcFacetResponse,
    StoryArcItemResponse,
    StoryArcResponse,
    TVEpisodeV1Response,
    TVSeasonV1Response,
    TVSeriesV1Response,
    public_item_kind,
)
from app.schemas.admin import (
    ProviderBatchHydrateRequest,
    ProviderBatchHydrateResponse,
    ProviderPreviewResponse,
)
from app.schemas.admin import (
    ProviderIngestRequest as ProviderPreviewRequest,
)
from app.schemas.metadata_shared import CreateEditionRequest, EditionResponse, SearchResult
from app.services.admin import AdminMetadataService
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])



@router.get("/metadata/media-types", response_model=MediaCatalogResponse)
async def media_type_catalog() -> MediaCatalogResponse:
    return MediaCatalogResponse(
        default_kind=ItemKind.comic,
        media_types=[
            _media_type_response(config)
            for config in top_level_media_types
        ],
    )


@router.get(
    "/metadata/normalized-manifest",
    response_model=MetadataNormalizedManifestResponse,
)
async def metadata_normalized_manifest() -> MetadataNormalizedManifestResponse:
    payload = normalized_metadata_manifest()
    kind_fields = {
        ItemKind(kind): fields
        for kind, fields in payload["kind_fields"].items()
    }
    return MetadataNormalizedManifestResponse(
        schema_version=payload["schema_version"],
        common_fields=payload["common_fields"],
        kind_fields=kind_fields,
        value_types=payload["value_types"],
    )


@router.get(
    "/metadata/field-schema",
    response_model=MetadataFieldSchemaResponse,
)
async def metadata_field_schema(
    editable_only: bool = Query(default=True),
) -> MetadataFieldSchemaResponse:
    """Unified field registry consumed by the admin + app edit surfaces.

    By default only user-editable fields are returned; pass
    ``editable_only=false`` to include internal normalization bookkeeping fields.
    """
    specs = [
        spec
        for spec in METADATA_FIELDS
        if spec.editable or not editable_only
    ]
    fields = [
        MetadataFieldSpecResponse(
            key=spec.key,
            value_type=spec.value_type,
            label=spec.label,
            common=spec.common,
            typed=spec.typed,
            normalized=spec.normalized,
            editable=spec.editable,
            section=spec.section,
            input=spec.input,
            kinds=sorted((kind for kind in spec.kinds), key=lambda k: k.value),
        )
        for spec in specs
    ]
    kind_fields = {
        kind: [spec.key for spec in fields_for_kind(kind, editable_only=editable_only)]
        for kind in ItemKind
    }
    sections: list[str] = []
    for spec in specs:
        if spec.section not in sections:
            sections.append(spec.section)
    return MetadataFieldSchemaResponse(
        schema_version=NORMALIZED_SCHEMA_VERSION,
        fields=fields,
        kind_fields=kind_fields,
        sections=sections,
    )


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


@router.get(
    "/barcode/{barcode}/providers",
    response_model=list[ProviderSearchResultResponse],
)
async def barcode_provider_search(
    barcode: str,
    db: DbSession,
    kind: ItemKind | None = None,
) -> list[ProviderSearchResultResponse]:
    results = await MetadataService(db).barcode_provider_search(barcode, kind)
    return [
        ProviderSearchResultResponse(
            provider=ExternalProvider(r.provider),
            provider_item_id=r.provider_item_id,
            title=r.title,
            kind=public_item_kind(r.kind),
            summary=r.summary,
            image_url=r.image_url,
            candidate_type=r.candidate_type,
            series_title=r.series_title,
            issue_number=r.issue_number,
            volume_start_year=r.volume_start_year,
            variant_name=r.variant_name,
            is_variant=r.is_variant,
            issue_count=r.issue_count,
            publisher=r.publisher,
            character_preview=r.character_preview,
            story_arc_preview=r.story_arc_preview,
        )
        for r in results
    ]


@router.get(
    "/metadata/providers/search",
    response_model=list[ProviderSearchResultResponse],
    dependencies=[Depends(provider_search_rate_limit)],
)
async def default_provider_search(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    kind: ItemKind = Query(...),
    series: str | None = Query(default=None, min_length=1, max_length=255),
    issue_number: str | None = Query(default=None, min_length=1, max_length=64),
    year: int | None = Query(default=None, ge=1800, le=2200),
) -> list[ProviderSearchResultResponse]:
    return await MetadataService(db).search_default_provider(
        q,
        kind,
        series=series,
        issue_number=issue_number,
        year=year,
    )


@router.get(
    "/metadata/providers/{provider}/search",
    response_model=list[ProviderSearchResultResponse],
    dependencies=[Depends(provider_search_rate_limit)],
)
async def provider_search(
    provider: ExternalProvider,
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    kind: ItemKind | None = None,
    series: str | None = Query(default=None, min_length=1, max_length=255),
    issue_number: str | None = Query(default=None, min_length=1, max_length=64),
    year: int | None = Query(default=None, ge=1800, le=2200),
) -> list[ProviderSearchResultResponse]:
    return await MetadataService(db).search_provider(
        provider,
        q,
        kind,
        series=series,
        issue_number=issue_number,
        year=year,
    )


@router.post(
    "/metadata/providers/preview",
    response_model=ProviderPreviewResponse,
    dependencies=[Depends(provider_search_rate_limit)],
)
async def provider_preview(
    payload: ProviderPreviewRequest,
    db: DbSession,
) -> ProviderPreviewResponse:
    from app.services.admin import AdminMetadataService

    return await AdminMetadataService(db).preview(payload)


@router.get("/metadata/providers/gcd/images/{provider_item_id}")
async def gcd_provider_image(
    provider_item_id: str,
    db: DbSession,
    series: str | None = Query(default=None, min_length=1, max_length=255),
    issue: str | None = Query(default=None, min_length=1, max_length=64),
    year: int | None = Query(default=None, ge=1800, le=2200),
    variant: str | None = Query(default=None, min_length=1, max_length=255),
) -> Response:
    cover = await GCDProvider().get_cover_image(
        provider_item_id,
        fallback=GCDCoverFallback(
            series_title=series,
            issue_number=issue,
            start_year=year,
            variant_hint=variant,
        ),
    )
    mirrored_url = await _mirror_gcd_cover_if_enabled(db, provider_item_id, cover)
    if mirrored_url is not None:
        return RedirectResponse(
            mirrored_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    if cover.redirect_url is not None:
        return RedirectResponse(
            cover.redirect_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return Response(
        content=cover.content or b"",
        media_type=cover.media_type or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/metadata/providers/mangadex/images/{provider_item_id}")
async def mangadex_provider_image(
    provider_item_id: str,
    db: DbSession,
) -> Response:
    provider = MangaDexProvider()
    provider_item = await provider.get_item(provider_item_id)
    normalized = await provider.normalize(provider_item.raw)
    cover_url = normalized.cover_image_url
    if not cover_url:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="mangadex_cover_not_found",
            detail="MangaDex cover image not found",
        )
    mirrored_url = await _mirror_mangadex_cover_if_enabled(db, provider_item_id, cover_url)
    if mirrored_url is not None:
        return RedirectResponse(
            mirrored_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    media_type, content = await _download_mangadex_cover(cover_url)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


async def _mirror_gcd_cover_if_enabled(
    db,
    provider_item_id: str,
    cover: GCDCoverImage,
) -> str | None:
    service = MetadataService(db)
    if cover.content is not None:
        return await service.mirror_provider_image_bytes(
            cover.content,
            source_url=cover.source_url,
            provider_name=ExternalProvider.gcd,
            provider_item_id=provider_item_id,
        )
    return await service.mirror_provider_image_url(
        cover.redirect_url,
        provider_name=ExternalProvider.gcd,
        provider_item_id=provider_item_id,
    )


async def _mirror_mangadex_cover_if_enabled(
    db,
    provider_item_id: str,
    cover_url: str,
) -> str | None:
    return await MetadataService(db).mirror_provider_image_url(
        cover_url,
        provider_name=ExternalProvider.mangadex,
        provider_item_id=provider_item_id,
    )


async def _download_mangadex_cover(url: str) -> tuple[str, bytes]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.image_download_timeout_seconds,
        ) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": settings.mangadex_user_agent,
                    "Referer": "https://mangadex.org/",
                    "Accept": "image/*",
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ApiHTTPException(
            status_code=exc.response.status_code,
            code="mangadex_cover_unavailable",
            detail=f"MangaDex cover request failed: HTTP {exc.response.status_code}",
        ) from exc
    except httpx.RequestError as exc:
        raise ApiHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="mangadex_cover_unavailable",
            detail=f"MangaDex cover request failed: {exc}",
        ) from exc

    media_type = response.headers.get("content-type", "application/octet-stream")
    if ";" in media_type:
        media_type = media_type.split(";", 1)[0].strip()
    return media_type or "application/octet-stream", response.content


@router.post(
    "/metadata/proposals",
    response_model=MetadataProposalResponse,
    status_code=201,
)
async def create_metadata_proposal(
    payload: MetadataProposalCreate,
    db: DbSession,
) -> MetadataProposalResponse:
    return await MetadataService(db).create_proposal(payload)


@router.post(
    "/story-arcs/facets",
    response_model=list[StoryArcFacetResponse],
)
async def get_story_arc_facets(
    db: DbSession,
    body: FacetItemIdsRequest,
) -> list[StoryArcFacetResponse]:
    return await MetadataService(db).get_story_arc_facets(body.item_ids)


@router.post(
    "/characters/facets",
    response_model=list[CharacterFacetResponse],
)
async def get_character_facets(
    db: DbSession,
    body: FacetItemIdsRequest,
) -> list[CharacterFacetResponse]:
    return await MetadataService(db).get_character_facets(body.item_ids)


@router.post(
    "/creators/facets",
    response_model=list[CreatorFacetResponse],
)
async def get_creator_facets(
    db: DbSession,
    body: FacetItemIdsRequest,
) -> list[CreatorFacetResponse]:
    return await MetadataService(db).get_creator_facets(body.item_ids)


@router.get("/metadata/books/works/{work_id}", response_model=BookWorkV1Response)
async def get_book_work(
    work_id: UUID,
    db: DbSession,
) -> BookWorkV1Response:
    return await MetadataService(db).get_book_work(work_id)


@router.get("/metadata/books/works/{work_id}/editions", response_model=list[BookEditionV1Response])
async def get_book_work_editions(
    work_id: UUID,
    db: DbSession,
) -> list[BookEditionV1Response]:
    return await MetadataService(db).get_book_work_editions(work_id)


@router.get("/metadata/books/editions/{edition_id}", response_model=BookEditionV1Response)
async def get_book_edition(
    edition_id: UUID,
    db: DbSession,
) -> BookEditionV1Response:
    return await MetadataService(db).get_book_edition(edition_id)


@router.get("/metadata/comics/works/{work_id}", response_model=ComicWorkV1Response)
async def get_comic_work(
    work_id: UUID,
    db: DbSession,
) -> ComicWorkV1Response:
    return await MetadataService(db).get_comic_work(work_id)


@router.get("/metadata/comics/works/{work_id}/issues", response_model=list[ComicIssueV1Response])
async def get_comic_work_issues(
    work_id: UUID,
    db: DbSession,
) -> list[ComicIssueV1Response]:
    return await MetadataService(db).get_comic_work_issues(work_id)


@router.get("/metadata/comics/issues/{issue_id}", response_model=ComicIssueV1Response)
async def get_comic_issue(
    issue_id: UUID,
    db: DbSession,
) -> ComicIssueV1Response:
    return await MetadataService(db).get_comic_issue(issue_id)


@router.get("/metadata/manga/works/{work_id}", response_model=MangaWorkV1Response)
async def get_manga_work(
    work_id: UUID,
    db: DbSession,
) -> MangaWorkV1Response:
    return await MetadataService(db).get_manga_work(work_id)


@router.get("/metadata/manga/works/{work_id}/chapters", response_model=list[MangaChapterV1Response])
async def get_manga_work_chapters(
    work_id: UUID,
    db: DbSession,
) -> list[MangaChapterV1Response]:
    return await MetadataService(db).get_manga_work_chapters(work_id)


@router.get("/metadata/manga/chapters/{chapter_id}", response_model=MangaChapterV1Response)
async def get_manga_chapter(
    chapter_id: UUID,
    db: DbSession,
) -> MangaChapterV1Response:
    return await MetadataService(db).get_manga_chapter(chapter_id)


@router.get("/metadata/anime/series/{series_id}", response_model=AnimeSeriesV1Response)
async def get_anime_series(
    series_id: UUID,
    db: DbSession,
) -> AnimeSeriesV1Response:
    return await MetadataService(db).get_anime_series(series_id)


@router.get(
    "/metadata/anime/series/{series_id}/episodes",
    response_model=list[AnimeEpisodeV1Response]
)
async def get_anime_series_episodes(
    series_id: UUID,
    db: DbSession,
) -> list[AnimeEpisodeV1Response]:
    return await MetadataService(db).get_anime_series_episodes(series_id)



@router.get("/metadata/anime/episodes/{episode_id}", response_model=AnimeEpisodeV1Response)
async def get_anime_episode(
    episode_id: UUID,
    db: DbSession,
) -> AnimeEpisodeV1Response:
    return await MetadataService(db).get_anime_episode(episode_id)


@router.get("/metadata/movies/works/{work_id}", response_model=MovieWorkV1Response)
async def get_movie_work(
    work_id: UUID,
    db: DbSession,
) -> MovieWorkV1Response:
    return await MetadataService(db).get_movie_work(work_id)


@router.get(
    "/metadata/movies/works/{work_id}/releases",
    response_model=list[MovieReleaseV1Response]
)
async def get_movie_work_releases(
    work_id: UUID,
    db: DbSession,
) -> list[MovieReleaseV1Response]:
    return await MetadataService(db).get_movie_work_releases(work_id)


@router.get("/metadata/movies/releases/{release_id}", response_model=MovieReleaseV1Response)
async def get_movie_release(
    release_id: UUID,
    db: DbSession,
) -> MovieReleaseV1Response:
    return await MetadataService(db).get_movie_release(release_id)


@router.get("/metadata/tv/series/{series_id}", response_model=TVSeriesV1Response)
async def get_tv_series(
    series_id: UUID,
    db: DbSession,
) -> TVSeriesV1Response:
    return await MetadataService(db).get_tv_series(series_id)


@router.get("/metadata/tv/series/{series_id}/seasons", response_model=list[TVSeasonV1Response])
async def get_tv_series_seasons(
    series_id: UUID,
    db: DbSession,
) -> list[TVSeasonV1Response]:
    return await MetadataService(db).get_tv_series_seasons(series_id)


@router.get("/metadata/tv/episodes/{episode_id}", response_model=TVEpisodeV1Response)
async def get_tv_episode(
    episode_id: UUID,
    db: DbSession,
) -> TVEpisodeV1Response:
    return await MetadataService(db).get_tv_episode(episode_id)


@router.get("/metadata/{media_type}/{item_id}", response_model=dict[str, Any] | BookWorkV1Response | ComicWorkV1Response)
async def get_metadata_item(
    media_type: str, item_id: UUID, db: DbSession
) -> dict[str, Any] | BookWorkV1Response | ComicWorkV1Response:
    return await _get_metadata_item(media_type, item_id, db)


@router.get("/{media_type}/{item_id}", response_model=dict[str, Any] | BookWorkV1Response | ComicWorkV1Response)
async def get_metadata_item_alias(
    media_type: str, item_id: UUID, db: DbSession
) -> dict[str, Any] | BookWorkV1Response | ComicWorkV1Response:
    return await _get_metadata_item(media_type, item_id, db)


async def _get_metadata_item(
    media_type: str, item_id: UUID, db: DbSession
) -> dict[str, Any] | BookWorkV1Response | ComicWorkV1Response:
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
        kind=public_item_kind(config.kind),
        singular_label=config.singular_label,
        plural_label=config.plural_label,
        route_segments=list(config.route_segments),
        default_provider=config.default_provider,
        providers=list(config.providers),
        provider_search_policy=config.provider_search_policy,
        is_top_level=config.is_top_level,
        grouping_model=config.grouping_model,
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


@router.get(
    "/metadata/providers/{provider}/seasons/{provider_item_id:path}",
    response_model=list[SeasonResponse],
)
async def get_provider_seasons(
    provider: ExternalProvider,
    provider_item_id: str,
    db: DbSession,
) -> list[SeasonResponse]:
    return await MetadataService(db).get_provider_seasons(provider, provider_item_id)


@router.get(
    "/metadata/providers/{provider}/volumes/{provider_item_id:path}",
    response_model=list[SeasonResponse],
)
async def get_provider_volumes(
    provider: ExternalProvider,
    provider_item_id: str,
    db: DbSession,
) -> list[SeasonResponse]:
    return await MetadataService(db).get_provider_volumes(provider, provider_item_id)


@router.get(
    "/metadata/items/{item_id}/volumes",
    response_model=list[SeasonResponse],
)
async def get_item_volumes(
    item_id: UUID,
    db: DbSession,
) -> list[SeasonResponse]:
    return await MetadataService(db).get_item_volumes(item_id)


@router.get(
    "/metadata/items/{item_id}/seasons",
    response_model=list[SeasonResponse],
)
async def get_item_seasons(
    item_id: UUID,
    db: DbSession,
) -> list[SeasonResponse]:
    return await MetadataService(db).get_item_seasons(item_id)


@router.post(
    "/metadata/items/{item_id}/editions",
    response_model=EditionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_item_edition(
    item_id: UUID,
    payload: CreateEditionRequest,
    db: DbSession,
    _user: CurrentUser,
) -> EditionResponse:
    return await MetadataService(db).create_edition(
        item_id,
        title=payload.title,
        format=payload.format,
        publisher=payload.publisher,
        isbn=payload.isbn,
        upc=payload.upc,
        language=payload.language,
        region=payload.region,
        release_date=payload.release_date,
    )


@router.get(
    "/story-arcs",
    response_model=list[StoryArcResponse],
)
async def search_story_arcs(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=200),
) -> list[StoryArcResponse]:
    return await MetadataService(db).search_story_arcs(q=q, limit=limit)


@router.get(
    "/story-arcs/{story_arc_id}/items",
    response_model=list[StoryArcItemResponse],
)
async def get_story_arc_items(
    story_arc_id: UUID,
    db: DbSession,
) -> list[StoryArcItemResponse]:
    return await MetadataService(db).get_story_arc_items(story_arc_id)


@router.get(
    "/creators",
    response_model=list[CreatorResponse],
)
async def search_creators(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=200),
) -> list[CreatorResponse]:
    return await MetadataService(db).search_creators(q=q, limit=limit)


@router.get(
    "/creators/{creator_id}/credits",
    response_model=list[CreatorCreditResponse],
)
async def get_creator_credits(
    creator_id: UUID,
    db: DbSession,
) -> list[CreatorCreditResponse]:
    return await MetadataService(db).get_creator_credits(creator_id)


@router.get(
    "/characters",
    response_model=list[CharacterResponse],
)
async def search_characters(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=200),
) -> list[CharacterResponse]:
    return await MetadataService(db).search_characters(q=q, limit=limit)


@router.get(
    "/characters/{character_id}/appearances",
    response_model=list[CharacterAppearanceResponse],
)
async def get_character_appearances(
    character_id: UUID,
    db: DbSession,
) -> list[CharacterAppearanceResponse]:
    return await MetadataService(db).get_character_appearances(character_id)


@router.post(
    "/providers/batch-hydrate",
    response_model=ProviderBatchHydrateResponse,
)
async def provider_batch_hydrate(
    payload: ProviderBatchHydrateRequest,
    db: DbSession,
) -> ProviderBatchHydrateResponse:
    return await AdminMetadataService(db).batch_hydrate(payload)
