from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.models.base import ExternalProvider, ItemKind, SeriesRelationType


class VariantResponse(BaseModel):
    id: UUID
    name: str
    variant_type: str | None
    sku: str | None
    barcode: str | None
    isbn: str | None
    region: str | None
    platform: str | None
    cover_price_cents: int | None
    currency: str | None
    cover_image_url: str | None
    thumbnail_image_url: str | None
    description: str | None
    physical_format: str | None = None
    physical_format_label: str | None = None
    metadata_json: dict[str, Any] | None
    is_primary: bool

    model_config = {"from_attributes": True}


class BundleReleaseContentSummaryResponse(BaseModel):
    total_items: int
    primary_count: int
    bonus_count: int


class BundleReleaseSummaryResponse(BaseModel):
    id: UUID
    kind: ItemKind
    title: str
    bundle_type: str | None = None
    format: str | None = None
    variant_type: str | None = None
    packaging_type: str | None = None
    region: str | None = None
    language: str | None = None
    publisher: str | None = None
    sku: str | None = None
    barcode: str | None = None
    release_date: date | None = None
    cover_image_url: str | None = None
    thumbnail_image_url: str | None = None
    primary_item_id: UUID | None = None
    primary_item_title: str | None = None
    series_id: UUID | None = None
    series_title: str | None = None
    volume_id: UUID | None = None
    volume_name: str | None = None
    content_summary: BundleReleaseContentSummaryResponse


class BundleReleaseMemberResponse(BaseModel):
    id: UUID
    item_id: UUID
    role: str
    sequence_number: int | None = None
    disc_number: int | None = None
    disc_label: str | None = None
    quantity: int
    is_primary: bool
    kind: ItemKind
    title: str
    item_number: str | None = None
    series_id: UUID | None = None
    series_title: str | None = None
    volume_name: str | None = None
    volume_number: int | None = None


class BundleReleaseDetailResponse(BundleReleaseSummaryResponse):
    franchise_id: UUID | None = None
    metadata_json: dict[str, Any] | None = None
    external_ids: dict[str, Any] | None = None
    members: list[BundleReleaseMemberResponse] = Field(default_factory=list)


class MetadataCredit(BaseModel):
    name: str
    role: str | None = None
    api_detail_url: str | None = None
    site_detail_url: str | None = None
    image_url: str | None = None

    model_config = {"extra": "allow"}


class ProviderLink(BaseModel):
    provider: ExternalProvider
    entity_type: str
    provider_item_id: str
    site_url: str | None = None
    api_url: str | None = None


class EditionResponse(BaseModel):
    id: UUID
    title: str
    format: str | None
    publisher: str | None
    isbn: str | None
    upc: str | None
    language: str | None
    region: str | None
    release_date: date | None
    physical_format: str | None = None
    physical_format_label: str | None = None
    metadata_json: dict[str, Any] | None
    variants: list[VariantResponse] = []

    model_config = {"from_attributes": True}


class CreateEditionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    format: str | None = None
    publisher: str | None = None
    isbn: str | None = None
    upc: str | None = None
    language: str | None = None
    region: str | None = None
    release_date: date | None = None


class ItemResponse(BaseModel):
    id: UUID
    kind: ItemKind
    title: str
    item_number: str | None
    sort_key: str | None
    synopsis: str | None
    release_type: str | None
    season_number: int | None
    episode_number: int | None
    runtime_minutes: int | None
    page_count: int | None
    metadata_json: dict[str, Any] | None
    series_id: UUID | None = None
    series_title: str | None = None
    volume_name: str | None = None
    volume_number: int | None = None
    volume_start_year: int | None = None
    publisher: str | None = None
    barcode: str | None = None
    cover_date: date | None = None
    store_date: date | None = None
    cover_price_cents: int | None = None
    currency: str | None = None
    catalog_number: str | None = None
    track_count: int | None = None
    tracks: list[dict[str, Any]] = []
    creators: list[MetadataCredit] = []
    characters: list[MetadataCredit] = []
    story_arcs: list[MetadataCredit] = []
    tags: list[str] = Field(default_factory=list)
    platforms: list[str] = []
    genres: list[str] = []
    country: str | None = None
    language: str | None = None
    age_rating: str | None = None
    imprint: str | None = None
    subtitle: str | None = None
    series_group: str | None = None
    release_status: str | None = None
    provider_links: list[ProviderLink] = []
    editions: list[EditionResponse] = []

    model_config = {"from_attributes": True}


class SearchResult(BaseModel):
    id: UUID
    kind: ItemKind
    title: str
    item_number: str | None = None
    synopsis: str | None = None
    runtime_minutes: int | None = None
    cover_image_url: str | None = None
    thumbnail_image_url: str | None = None
    edition_title: str | None = None
    physical_format: str | None = None
    physical_format_label: str | None = None
    publisher: str | None = None
    release_date: date | None = None
    release_year: int | None = None
    barcode: str | None = None
    variant: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    track_count: int | None = None
    tracks: list[dict[str, Any]] | None = None
    catalog_number: str | None = None
    creators: list[dict[str, Any]] | None = None
    characters: list[str] | None = None
    story_arcs: list[str] | None = None
    platforms: list[str] | None = None
    genres: list[str] | None = None
    page_count: int | None = None
    cover_price_cents: int | None = None
    currency: str | None = None
    country: str | None = None
    release_status: str | None = None
    language: str | None = None
    age_rating: str | None = None
    imprint: str | None = None
    subtitle: str | None = None
    series_group: str | None = None
    bundle_titles: list[str] | None = None
    bundle_release_ids: list[str] | None = None


class ProviderSearchResultResponse(BaseModel):
    provider: ExternalProvider
    provider_item_id: str
    title: str
    kind: ItemKind
    summary: str | None = None
    image_url: str | None = None
    candidate_type: str | None = None
    series_title: str | None = None
    issue_number: str | None = None
    volume_start_year: int | None = None
    variant_name: str | None = None
    is_variant: bool | None = None
    issue_count: int | None = None
    publisher: str | None = None
    character_preview: list[str] = Field(default_factory=list)
    story_arc_preview: list[str] = Field(default_factory=list)


class PhysicalFormatResponse(BaseModel):
    id: str
    label: str
    media_family: str
    variant_type: str
    aliases: list[str] = Field(default_factory=list)


class MediaTypeResponse(BaseModel):
    kind: ItemKind
    singular_label: str
    plural_label: str
    route_segments: list[str]
    default_provider: ExternalProvider | None = None
    providers: list[ExternalProvider] = Field(default_factory=list)
    provider_search_policy: str
    is_top_level: bool = True
    legacy_of: ItemKind | None = None
    physical_formats: list[PhysicalFormatResponse] = Field(default_factory=list)


class MediaCatalogResponse(BaseModel):
    contract_version: int
    snapshot_schema_version: int
    default_kind: ItemKind
    media_types: list[MediaTypeResponse]


class MetadataProposalCreate(BaseModel):
    provider: ExternalProvider
    provider_item_id: str | None = Field(default=None, max_length=255)
    query: str = Field(min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    image_url: str | None = Field(default=None, max_length=1024)
    metadata_payload: dict[str, Any] | None = None


class MetadataProposalResponse(BaseModel):
    id: UUID
    provider: ExternalProvider
    provider_item_id: str | None
    query: str
    title: str | None
    metadata_payload: dict[str, Any] | None = None
    status: str

    model_config = {"from_attributes": True}


class SeriesResponse(BaseModel):
    id: UUID
    kind: ItemKind
    title: str
    description: str | None = None
    original_title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    language: str | None = None
    country: str | None = None
    tags: list[str] = Field(default_factory=list)
    volume_count: int = 0
    item_count: int = 0


class SeriesItemResponse(BaseModel):
    series_id: UUID
    item_id: UUID
    kind: ItemKind
    title: str
    item_number: str | None = None
    volume_name: str | None = None
    volume_number: int | None = None
    cover_image_url: str | None = None


class SeriesRelationResponse(BaseModel):
    id: UUID
    relation_type: SeriesRelationType
    target_series_id: UUID
    target_series_title: str
    target_series_kind: ItemKind
    ordinal: int | None = None
    image_url: str | None = None
    start_year: int | None = None
    provider: str | None = None
    provider_id: str | None = None


class EpisodeResponse(BaseModel):
    episode_number: int
    title: str
    overview: str | None = None
    air_date: date | None = None
    runtime_minutes: int | None = None
    page_count: int | None = None
    still_url: str | None = None


class SeasonResponse(BaseModel):
    season_number: int
    title: str
    overview: str | None = None
    air_date: date | None = None
    episode_count: int | None = None
    poster_url: str | None = None
    episodes: list[EpisodeResponse] = Field(default_factory=list)


class StoryArcResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    publisher: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    item_count: int = 0


class StoryArcFacetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    publisher: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    item_count: int = 0
    item_ids: list[UUID] = Field(default_factory=list)


class StoryArcItemResponse(BaseModel):
    story_arc_id: UUID
    item_id: UUID
    ordinal: int | None = None
    kind: ItemKind
    title: str
    item_number: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    cover_image_url: str | None = None


class CreatorResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    image_url: str | None = None
    api_detail_url: str | None = None
    site_detail_url: str | None = None
    item_count: int = 0


class CreatorFacetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    image_url: str | None = None
    item_count: int = 0
    item_ids: list[UUID] = Field(default_factory=list)
    role_counts: dict[str, int] = Field(default_factory=dict)


class CreatorCreditResponse(BaseModel):
    creator_id: UUID
    item_id: UUID
    role: str
    kind: ItemKind
    title: str
    item_number: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    cover_image_url: str | None = None


class CharacterResponse(BaseModel):
    id: UUID
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    image_url: str | None = None
    first_appearance_item_id: UUID | None = None
    appearance_count: int = 0


class CharacterFacetResponse(BaseModel):
    id: UUID
    name: str
    aliases: list[str] = Field(default_factory=list)
    image_url: str | None = None
    item_count: int = 0
    item_ids: list[UUID] = Field(default_factory=list)
    role_counts: dict[str, int] = Field(default_factory=dict)


class FacetItemIdsRequest(BaseModel):
    item_ids: list[UUID] = Field(default_factory=list)


class CharacterAppearanceResponse(BaseModel):
    character_id: UUID
    item_id: UUID
    role: str
    kind: ItemKind
    title: str
    item_number: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    cover_image_url: str | None = None


def item_response_from_model(
    item: Any, extra_provider_links: list[ProviderLink] | None = None
) -> ItemResponse:
    base = ItemResponse.model_validate(item).model_dump()
    _enrich_physical_formats(base, item)
    edition = _primary_edition(item)
    variant = _primary_variant(item)
    source = _source_metadata(edition)
    normalized = _normalized_metadata(edition)
    volume = getattr(item, "volume", None)
    series = getattr(volume, "series", None) if volume is not None else None
    base.update(
        {
            "series_id": str(getattr(series, "id", None)) if series else None,
            "series_title": getattr(series, "title", None),
            "volume_name": getattr(volume, "name", None),
            "volume_number": getattr(volume, "volume_number", None),
            "volume_start_year": getattr(volume, "start_year", None),
            "publisher": _publisher(item),
            "barcode": _barcode(item),
            "cover_date": _date_value(source.get("cover_date")),
            "store_date": _date_value(source.get("store_date")),
            "cover_price_cents": getattr(variant, "cover_price_cents", None),
            "currency": getattr(variant, "currency", None),
            "catalog_number": _optional_text(normalized.get("catalog_number")),
            "track_count": _optional_int(normalized.get("track_count")),
            "tracks": _tracks(normalized.get("tracks")),
            "creators": _credits(source.get("person_credits"))
            or _credits(normalized.get("creators")),
            "characters": _credits(source.get("character_credits"))
            or _credits(normalized.get("characters")),
            "story_arcs": _credits(source.get("story_arc_credits"))
            or _credits(normalized.get("story_arcs")),
            "platforms": _string_list(normalized.get("platforms")),
            "genres": _string_list(normalized.get("genres")),
            "country": _optional_text(normalized.get("country")),
            "language": _optional_text(getattr(edition, "language", None))
            or _optional_text(normalized.get("language")),
            "age_rating": _optional_text(normalized.get("age_rating")),
            "imprint": _optional_text(normalized.get("imprint")),
            "subtitle": _optional_text(normalized.get("subtitle")),
            "series_group": _optional_text(normalized.get("series_group")),
            "release_status": _optional_text(normalized.get("release_status")),
            "provider_links": _provider_links(item, extra_provider_links=extra_provider_links),
        }
    )
    return ItemResponse(**base)


def bundle_release_summary_from_model(bundle_release: Any) -> BundleReleaseSummaryResponse:
    primary_item = getattr(bundle_release, "primary_item", None)
    series = getattr(bundle_release, "series", None)
    volume = getattr(bundle_release, "volume", None)
    items = list(getattr(bundle_release, "items", []) or [])
    primary_count = sum(1 for member in items if getattr(member, "is_primary", False))
    return BundleReleaseSummaryResponse(
        id=bundle_release.id,
        kind=bundle_release.kind,
        title=bundle_release.title,
        bundle_type=getattr(bundle_release, "bundle_type", None),
        format=getattr(bundle_release, "format", None),
        variant_type=getattr(bundle_release, "variant_type", None),
        packaging_type=getattr(bundle_release, "packaging_type", None),
        region=getattr(bundle_release, "region", None),
        language=getattr(bundle_release, "language", None),
        publisher=getattr(bundle_release, "publisher", None),
        sku=getattr(bundle_release, "sku", None),
        barcode=getattr(bundle_release, "barcode", None),
        release_date=getattr(bundle_release, "release_date", None),
        cover_image_url=getattr(bundle_release, "cover_image_url", None),
        thumbnail_image_url=getattr(bundle_release, "thumbnail_image_url", None),
        primary_item_id=getattr(primary_item, "id", None),
        primary_item_title=getattr(primary_item, "title", None),
        series_id=getattr(series, "id", None),
        series_title=getattr(series, "title", None),
        volume_id=getattr(volume, "id", None),
        volume_name=getattr(volume, "name", None),
        content_summary=BundleReleaseContentSummaryResponse(
            total_items=len(items),
            primary_count=primary_count,
            bonus_count=max(len(items) - primary_count, 0),
        ),
    )


def bundle_release_member_sort_key(member: Any) -> tuple[bool, int, bool, int, str]:
    item = getattr(member, "item", None)
    item_title = getattr(item, "title", None)
    title_key = str(item_title).casefold() if item_title is not None else str(getattr(member, "id", ""))
    return (
        getattr(member, "disc_number", None) is None,
        getattr(member, "disc_number", None) or 0,
        getattr(member, "sequence_number", None) is None,
        getattr(member, "sequence_number", None) or 0,
        title_key,
    )


def bundle_release_detail_from_model(bundle_release: Any) -> BundleReleaseDetailResponse:
    summary = bundle_release_summary_from_model(bundle_release)
    members = sorted(
        list(getattr(bundle_release, "items", []) or []),
        key=bundle_release_member_sort_key,
    )
    return BundleReleaseDetailResponse(
        **summary.model_dump(),
        franchise_id=getattr(bundle_release, "franchise_id", None),
        metadata_json=getattr(bundle_release, "metadata_json", None),
        external_ids=getattr(bundle_release, "external_ids", None),
        members=[
            BundleReleaseMemberResponse(
                id=member.id,
                item_id=member.item_id,
                role=member.role,
                sequence_number=getattr(member, "sequence_number", None),
                disc_number=getattr(member, "disc_number", None),
                disc_label=getattr(member, "disc_label", None),
                quantity=getattr(member, "quantity", 1),
                is_primary=getattr(member, "is_primary", False),
                kind=member.item.kind,
                title=member.item.title,
                item_number=getattr(member.item, "item_number", None),
                series_id=getattr(getattr(getattr(member.item, "volume", None), "series", None), "id", None),
                series_title=getattr(getattr(getattr(member.item, "volume", None), "series", None), "title", None),
                volume_name=getattr(getattr(member.item, "volume", None), "name", None),
                volume_number=getattr(getattr(member.item, "volume", None), "volume_number", None),
            )
            for member in members
        ],
    )


def _enrich_physical_formats(base: dict[str, Any], item: Any) -> None:
    kind = getattr(item, "kind", None)
    response_editions = base.get("editions")
    source_editions = list(getattr(item, "editions", []) or [])
    if not isinstance(response_editions, list):
        return
    for response_edition, source_edition in zip(response_editions, source_editions, strict=False):
        if not isinstance(response_edition, dict):
            continue
        physical_format = _physical_format_payload(
            getattr(source_edition, "metadata_json", None),
            fallback_format=getattr(source_edition, "format", None),
            kind=kind,
        )
        if physical_format is not None:
            response_edition.update(physical_format)
        response_variants = response_edition.get("variants")
        source_variants = list(getattr(source_edition, "variants", []) or [])
        if not isinstance(response_variants, list):
            continue
        for response_variant, source_variant in zip(
            response_variants,
            source_variants,
            strict=False,
        ):
            if not isinstance(response_variant, dict):
                continue
            variant_format = _physical_format_payload(
                getattr(source_variant, "metadata_json", None),
                fallback_format=None,
                kind=kind,
            )
            if variant_format is None:
                variant_format = physical_format
            if variant_format is not None:
                response_variant.update(variant_format)


def _physical_format_payload(
    metadata: dict[str, Any] | None,
    *,
    fallback_format: str | None,
    kind: Any,
) -> dict[str, str] | None:
    metadata_format = _metadata_physical_format(metadata)
    config = physical_format_for_id(metadata_format) if metadata_format else None
    if config is None and fallback_format and is_video_item_kind(kind):
        config = physical_format_for_id(fallback_format)
    if config is None:
        return None
    return {
        "physical_format": config.id,
        "physical_format_label": config.label,
    }


def _metadata_physical_format(metadata: dict[str, Any] | None) -> str | None:
    if not isinstance(metadata, dict):
        return None
    normalized = metadata.get("normalized")
    if isinstance(normalized, dict):
        physical_format = normalized.get("physical_format")
        if physical_format:
            return str(physical_format)
    physical_format = metadata.get("physical_format")
    return str(physical_format) if physical_format else None


def _primary_edition(item: Any) -> Any | None:
    editions = list(getattr(item, "editions", []) or [])
    return editions[0] if editions else None


def _primary_variant(item: Any) -> Any | None:
    for edition in getattr(item, "editions", []) or []:
        variants = list(getattr(edition, "variants", []) or [])
        primary = next((variant for variant in variants if variant.is_primary), None)
        if primary is not None:
            return primary
        if variants:
            return variants[0]
    return None


def _source_metadata(edition: Any | None) -> dict[str, Any]:
    metadata = getattr(edition, "metadata_json", None) or {}
    source = metadata.get("source") if isinstance(metadata, dict) else None
    return source if isinstance(source, dict) else {}


def _normalized_metadata(edition: Any | None) -> dict[str, Any]:
    metadata = getattr(edition, "metadata_json", None) or {}
    normalized = metadata.get("normalized") if isinstance(metadata, dict) else None
    return normalized if isinstance(normalized, dict) else {}


def _publisher(item: Any) -> str | None:
    for edition in getattr(item, "editions", []) or []:
        if edition.publisher:
            return edition.publisher
    return None


def _barcode(item: Any) -> str | None:
    for edition in getattr(item, "editions", []) or []:
        if edition.upc:
            return edition.upc
        if edition.isbn:
            return edition.isbn
        for variant in getattr(edition, "variants", []) or []:
            if variant.barcode:
                return variant.barcode
            if variant.isbn:
                return variant.isbn
    return None


def _date_value(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _credits(values: Any) -> list[MetadataCredit]:
    if not isinstance(values, list):
        return []
    credits: list[MetadataCredit] = []
    for value in values:
        if isinstance(value, str):
            credits.append(MetadataCredit(name=value))
            continue
        if not isinstance(value, dict):
            continue
        name = value.get("name")
        if not name:
            continue
        role = value.get("role") or value.get("roles")
        if isinstance(role, list):
            role = ", ".join(str(item) for item in role if item)
        credits.append(
            MetadataCredit(
                name=str(name),
                role=str(role) if role else None,
                api_detail_url=_optional_text(value.get("api_detail_url")),
                site_detail_url=_optional_text(value.get("site_detail_url")),
                image_url=_optional_text(value.get("image_url")),
            )
        )
    return credits


def _tracks(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    tracks: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        title = _optional_text(value.get("title"))
        if title is None:
            continue
        track: dict[str, Any] = {"title": title}
        position = _optional_int(value.get("position"))
        if position is not None:
            track["position"] = position
        duration_seconds = _optional_int(value.get("duration_seconds"))
        if duration_seconds is not None:
            track["duration_seconds"] = duration_seconds
        artist = _optional_text(value.get("artist"))
        if artist is not None:
            track["artist"] = artist
        disc_number = _optional_int(value.get("disc_number"))
        if disc_number is not None:
            track["disc_number"] = disc_number
        tracks.append(track)
    return tracks


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        text = _optional_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _provider_links(
    item: Any, extra_provider_links: list[ProviderLink] | None = None
) -> list[ProviderLink]:
    links: list[ProviderLink] = []
    seen: dict[tuple[str, str, str], ProviderLink] = {}
    for link in extra_provider_links or []:
        _append_provider_link(
            links,
            seen,
            provider=link.provider.value,
            entity_type=link.entity_type,
            provider_item_id=link.provider_item_id,
            site_url=link.site_url,
            api_url=link.api_url,
        )
    for edition in getattr(item, "editions", []) or []:
        metadata = getattr(edition, "metadata_json", None) or {}
        provider = metadata.get("provider") if isinstance(metadata, dict) else None
        provider_item_id = metadata.get("provider_item_id") if isinstance(metadata, dict) else None
        source = _source_metadata(edition)
        if provider and provider_item_id:
            _append_provider_link(
                links,
                seen,
                provider=str(provider),
                entity_type="item",
                provider_item_id=str(provider_item_id),
                site_url=_optional_text(source.get("site_detail_url")),
                api_url=_optional_text(source.get("api_detail_url")),
            )
    return links


def _append_provider_link(
    links: list[ProviderLink],
    seen: dict[tuple[str, str, str], ProviderLink],
    *,
    provider: str,
    entity_type: str,
    provider_item_id: str,
    site_url: str | None = None,
    api_url: str | None = None,
) -> None:
    key = (provider, entity_type, provider_item_id)
    existing = seen.get(key)
    if existing is not None:
        if existing.site_url is None and site_url is not None:
            existing.site_url = site_url
        if existing.api_url is None and api_url is not None:
            existing.api_url = api_url
        return
    try:
        provider_enum = ExternalProvider(provider)
    except ValueError:
        return
    link = ProviderLink(
        provider=provider_enum,
        entity_type=entity_type,
        provider_item_id=provider_item_id,
        site_url=site_url,
        api_url=api_url,
    )
    seen[key] = link
    links.append(link)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
