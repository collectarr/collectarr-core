from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.catalog.grouping_models import GroupingModel
from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.metadata_normalized import typed_kind_metadata_for_item
from app.models.base import ExternalProvider, ItemKind
from app.schemas.metadata_shared import (
    BundleReleaseContentSummaryResponse,
    BundleReleaseDetailResponse,
    BundleReleaseMemberResponse,
    BundleReleaseSummaryResponse,
    ContributorResponse,
    ExternalProviderIdResponse,
    MetadataCredit,
    public_item_kind,
)

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
    grouping_model: GroupingModel
    physical_formats: list[PhysicalFormatResponse] = Field(default_factory=list)


class MediaCatalogResponse(BaseModel):
    default_kind: ItemKind
    media_types: list[MediaTypeResponse]


class MetadataNormalizedManifestResponse(BaseModel):
    schema_version: int
    common_fields: list[str]
    kind_fields: dict[ItemKind, list[str]]
    value_types: dict[str, str]


class MetadataFieldSpecResponse(BaseModel):
    """A single editable canonical metadata field, rendered from the registry."""

    key: str
    value_type: str
    label: str
    common: bool
    typed: bool
    normalized: bool
    editable: bool
    section: str
    input: str
    kinds: list[ItemKind] = Field(default_factory=list)


class MetadataFieldSchemaResponse(BaseModel):
    """The unified field schema consumed by the admin + app edit surfaces."""

    schema_version: int
    fields: list[MetadataFieldSpecResponse]
    kind_fields: dict[ItemKind, list[str]]
    sections: list[str] = Field(default_factory=list)


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


class EpisodeResponse(BaseModel):
    episode_number: int
    title: str
    provider_item_id: str | None = None
    overview: str | None = None
    air_date: date | None = None
    runtime_minutes: int | None = None
    page_count: int | None = None


class SeasonResponse(BaseModel):
    season_number: int
    title: str
    provider_item_id: str | None = None
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


class AttrDict(dict):
    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    __setattr__ = dict.__setitem__


def _attr_dict(value: Any) -> Any:
    if isinstance(value, dict):
        return AttrDict({key: _attr_dict(inner) for key, inner in value.items()})
    if isinstance(value, list):
        return [_attr_dict(entry) for entry in value]
    return value


def item_response_from_model(
    item: Any, extra_provider_links: list[ExternalProviderIdResponse] | None = None
) -> dict[str, Any]:
    """DEPRECATED: Converts legacy Item model to dictionary response."""
    base = {
        "id": getattr(item, "id", None),
        "kind": public_item_kind(getattr(item, "kind", None)),
        "title": getattr(item, "title", None),
        "title_extension": getattr(item, "title_extension", None),
        "item_number": getattr(item, "item_number", None),
        "sort_key": getattr(item, "sort_key", None),
        "synopsis": getattr(item, "synopsis", None),
        "release_type": getattr(item, "release_type", None),
        "season_number": getattr(item, "season_number", None),
        "episode_number": getattr(item, "episode_number", None),
        "runtime_minutes": getattr(item, "runtime_minutes", None),
        "page_count": getattr(item, "page_count", None),
        "editions": [
            {
                "id": str(getattr(ed, "id", None)) if getattr(ed, "id", None) else None,
                "title": getattr(ed, "title", None),
                "format": getattr(ed, "format", None),
                "publisher": getattr(ed, "publisher", None),
                "isbn": getattr(ed, "isbn", None),
                "upc": getattr(ed, "upc", None),
                "language": getattr(ed, "language", None),
                "region": getattr(ed, "region", None),
                "imprint": getattr(ed, "imprint", None),
                "subtitle": getattr(ed, "subtitle", None),
                "series_group": getattr(ed, "series_group", None),
                "age_rating": getattr(ed, "age_rating", None),
                "catalog_number": getattr(ed, "catalog_number", None),
                "release_status": getattr(ed, "release_status", None),
                "nr_discs": getattr(ed, "nr_discs", None),
                "screen_ratio": getattr(ed, "screen_ratio", None),
                "audio_tracks": getattr(ed, "audio_tracks", None),
                "subtitles": getattr(ed, "subtitles", None),
                "layers": getattr(ed, "layers", None),
                "release_date": getattr(ed, "release_date", None),
                "variants": [
                    {
                        "id": str(getattr(variant, "id", None)) if getattr(variant, "id", None) else None,
                        "name": getattr(variant, "name", None),
                        "variant_type": getattr(variant, "variant_type", None),
                        "sku": getattr(variant, "sku", None),
                        "barcode": getattr(variant, "barcode", None),
                        "isbn": getattr(variant, "isbn", None),
                        "region": getattr(variant, "region", None),
                        "platform": getattr(variant, "platform", None),
                        "cover_price_cents": getattr(variant, "cover_price_cents", None),
                        "currency": getattr(variant, "currency", None),
                        "cover_image_url": getattr(variant, "cover_image_url", None),
                        "thumbnail_image_url": getattr(variant, "thumbnail_image_url", None),
                        "description": getattr(variant, "description", None),
                        "physical_format": getattr(variant, "physical_format", None),
                        "physical_format_label": getattr(variant, "physical_format_label", None),
                        "is_primary": getattr(variant, "is_primary", False),
                    }
                    for variant in (getattr(ed, "variants", []) or [])
                ],
            }
            for ed in (getattr(item, "editions", []) or [])
        ],
    }
    _enrich_physical_formats(base, item)
    _apply_organization_overrides(base, item)
    edition = _primary_edition(item)
    variant = _primary_variant(item)
    source = _source_metadata(edition)
    typed_normalized = _typed_kind_metadata(item)
    edition_normalized = _normalized_metadata(edition)
    creators = _creator_credits(item)
    characters = _character_credits(item)
    story_arcs = _story_arc_credits(item)
    volume = getattr(item, "volume", None)
    series = getattr(volume, "__dict__", {}).get("series") if volume is not None else None
    base.update(
        {
            "series_id": str(getattr(volume, "series_id", None)) if volume is not None else None,
            "series_title": getattr(series, "title", None) if series is not None else getattr(volume, "name", None),
            "volume_name": getattr(volume, "name", None),
            "volume_number": getattr(volume, "volume_number", None),
            "volume_start_year": getattr(volume, "start_year", None),
            "publisher": _publisher(item),
            "barcode": _barcode(item),
            "cover_date": _date_value(source.get("cover_date")),
            "store_date": _date_value(source.get("store_date")),
            "localized_title": _optional_text(getattr(item, "localized_title", None)),
            "original_title": _optional_text(getattr(item, "original_title", None)),
            "search_aliases": _string_list(getattr(item, "search_aliases", None)),
            "crossover": _optional_text(getattr(item, "crossover", None)),
            "plot_summary": _optional_text(getattr(item, "plot_summary", None)),
            "plot_description": _optional_text(getattr(item, "plot_description", None)),
            "cover_price_cents": getattr(variant, "cover_price_cents", None),
            "currency": getattr(variant, "currency", None),
            "catalog_number": _optional_text(getattr(edition, "catalog_number", None)),
            "track_count": _optional_int(typed_normalized.get("track_count")),
            "tracks": _tracks(typed_normalized.get("tracks")),
            "creators": creators,
            "characters": characters,
            "character_details": characters,
            "story_arcs": story_arcs,
            "platforms": _string_list(typed_normalized.get("platforms")),
            "genres": _string_list(typed_normalized.get("genres")),
            "country": _optional_text(getattr(edition, "region", None)),
            "language": _optional_text(getattr(edition, "language", None)),
            "age_rating": _optional_text(getattr(edition, "age_rating", None)),
            "audience_rating": _optional_text(typed_normalized.get("audience_rating")),
            "color": _optional_text(typed_normalized.get("color")),
            "nr_discs": (
                _optional_int(getattr(edition, "nr_discs", None))
                or _optional_int(edition_normalized.get("nr_discs"))
            ),
            "screen_ratio": (
                _optional_text(getattr(edition, "screen_ratio", None))
                or _optional_text(edition_normalized.get("screen_ratio"))
            ),
            "audio_tracks": (
                _optional_text(getattr(edition, "audio_tracks", None))
                or _optional_text(edition_normalized.get("audio_tracks"))
            ),
            "subtitles": (
                _optional_text(getattr(edition, "subtitles", None))
                or _optional_text(edition_normalized.get("subtitles"))
            ),
            "layers": (
                _optional_text(getattr(edition, "layers", None))
                or _optional_text(edition_normalized.get("layers"))
            ),
            "imprint": _imprint(item, edition),
            "subtitle": _optional_text(getattr(edition, "subtitle", None)),
            "series_group": _optional_text(getattr(edition, "series_group", None)),
            "release_status": _optional_text(getattr(edition, "release_status", None)),
            "trailer_urls": _link_payload_list(item, "trailer_urls"),
            "external_links": _link_payload_list(item, "external_links"),
            "provider_links": _provider_links(item, extra_provider_links=extra_provider_links),
        }
    )
    return _attr_dict(base)



def bundle_release_summary_from_model(bundle_release: Any) -> BundleReleaseSummaryResponse:
    primary_item = getattr(bundle_release, "primary_item", None)
    series = getattr(bundle_release, "series", None)
    volume = getattr(bundle_release, "volume", None)
    items = list(getattr(bundle_release, "items", []) or [])
    primary_count = sum(1 for member in items if getattr(member, "is_primary", False))
    return BundleReleaseSummaryResponse(
        id=bundle_release.id,
        kind=public_item_kind(getattr(bundle_release, "kind", None)),
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


def bundle_release_detail_from_model(
    bundle_release: Any,
    *,
    provider_links: list[Any] | None = None,
) -> BundleReleaseDetailResponse:
    summary = bundle_release_summary_from_model(bundle_release)
    members = sorted(
        getattr(bundle_release, "items", []) or [],
        key=bundle_release_member_sort_key,
    )
    loaded_provider_links = provider_links
    if loaded_provider_links is None:
        loaded_provider_links = _provider_links_from_models(
            getattr(bundle_release, "provider_links", []),
            entity_type="bundle_release",
        )
    external_provider_links = [
        ExternalProviderIdResponse.model_validate(link) for link in loaded_provider_links
    ]
    return BundleReleaseDetailResponse(
        **summary.model_dump(),
        franchise_id=getattr(bundle_release, "franchise_id", None),
        provider_links=external_provider_links,
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
                kind=public_item_kind(getattr(member.item, "kind", None)),
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
            preferred={
                "physical_format": getattr(source_edition, "physical_format", None),
                "physical_format_label": getattr(source_edition, "physical_format_label", None),
            },
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
                preferred={
                    "physical_format": getattr(source_variant, "physical_format", None),
                    "physical_format_label": getattr(source_variant, "physical_format_label", None),
                },
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
    preferred: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    preferred_format = _optional_text((preferred or {}).get("physical_format"))
    preferred_label = _optional_text((preferred or {}).get("physical_format_label"))
    if preferred_format:
        config = physical_format_for_id(preferred_format)
        if config is not None:
            return {
                "physical_format": config.id,
                "physical_format_label": config.label,
            }
        if preferred_label:
            return {
                "physical_format": preferred_format,
                "physical_format_label": preferred_label,
            }
    config = None
    if config is None and fallback_format and is_video_item_kind(kind):
        config = physical_format_for_id(fallback_format)
    if config is None:
        return None
    return {
        "physical_format": config.id,
        "physical_format_label": config.label,
    }


def _normalized_item_metadata(item: Any) -> dict[str, Any]:
    metadata = getattr(item, "metadata_json", None) or {}
    normalized = metadata.get("normalized") if isinstance(metadata, dict) else None
    return normalized if isinstance(normalized, dict) else {}


def _typed_kind_metadata(item: Any) -> dict[str, Any]:
    return typed_kind_metadata_for_item(item)


def _source_item_metadata(item: Any) -> dict[str, Any]:
    metadata = getattr(item, "metadata_json", None) or {}
    provider = metadata.get("provider") if isinstance(metadata, dict) else None
    provider_item_id = metadata.get("provider_item_id") if isinstance(metadata, dict) else None
    source = {
        "provider": provider,
        "provider_item_id": provider_item_id,
    }
    normalized = _normalized_item_metadata(item)
    for key in ("cover_image_url", "thumbnail_image_url"):
        value = _optional_text(normalized.get(key))
        if value is not None:
            source[key] = value
    return {key: value for key, value in source.items() if value is not None}


def _link_payload_list(item: Any, key: str) -> list[dict[str, Any]]:
    values = getattr(item, key, None)
    if not isinstance(values, list):
        return []
    normalized: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        url = _optional_text(value.get("url"))
        if url is None:
            continue
        entry: dict[str, Any] = {"url": url}
        for field in ("site", "name", "kind", "description"):
            text = _optional_text(value.get(field))
            if text is not None:
                entry[field] = text
        normalized.append(entry)
    return normalized


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


def _loaded_rows(entity: Any, attr_name: str) -> list[Any]:
    values = getattr(entity, "__dict__", {}).get(attr_name)
    if values is None:
        return []
    return list(values)


def _creator_credits(item: Any) -> list[MetadataCredit]:
    rows = sorted(
        _loaded_rows(item, "creator_links"),
        key=lambda link: (
            getattr(link, "created_at", None) is None,
            getattr(link, "created_at", None),
            str(getattr(link, "id", "") or ""),
        ),
    )
    credits: list[MetadataCredit] = []
    for link in rows:
        person = getattr(link, "person", None)
        if person is None or not getattr(person, "name", None):
            continue
        person_metadata = getattr(person, "metadata_json", None)
        if not isinstance(person_metadata, dict):
            person_metadata = {}
        credits.append(
            MetadataCredit(
                name=person.name,
                role=link.role,
                api_detail_url=_optional_text(person_metadata.get("api_detail_url")),
                site_detail_url=_optional_text(person_metadata.get("site_detail_url")),
                image_url=_optional_text(person_metadata.get("image_url")),
            )
        )
    return credits


def _character_credits(item: Any) -> list[MetadataCredit]:
    rows = sorted(
        _loaded_rows(item, "character_appearances"),
        key=lambda appearance: (
            getattr(appearance, "created_at", None) is None,
            getattr(appearance, "created_at", None),
            str(getattr(appearance, "id", "") or ""),
        ),
    )
    return [
        MetadataCredit(
            name=appearance.character.name,
            role=appearance.role,
            aliases=[
                str(alias) for alias in (getattr(appearance.character, "aliases", None) or []) if str(alias).strip()
            ],
            description=getattr(appearance.character, "description", None),
            image_url=getattr(appearance.character, "image_url", None),
            first_appearance_item_id=getattr(appearance.character, "first_appearance_item_id", None),
        )
        for appearance in rows
        if getattr(appearance, "character", None) is not None
        and getattr(appearance.character, "name", None)
    ]


def _story_arc_credits(item: Any) -> list[MetadataCredit]:
    rows = sorted(
        _loaded_rows(item, "story_arc_items"),
        key=lambda link: (
            getattr(link, "ordinal", None) is None,
            getattr(link, "ordinal", None) or 0,
            str(getattr(getattr(link, "story_arc", None), "name", "") or "").casefold(),
        ),
    )
    return [
        MetadataCredit(
            name=link.story_arc.name,
            description=getattr(link.story_arc, "description", None),
            ordinal=getattr(link, "ordinal", None),
            publisher=getattr(link.story_arc, "publisher", None),
        )
        for link in rows
        if getattr(link, "story_arc", None) is not None and getattr(link.story_arc, "name", None)
    ]


def _publisher(item: Any) -> str | None:
    publisher = _organization_name(item, "publisher")
    if publisher is not None:
        return publisher
    for edition in getattr(item, "editions", []) or []:
        if edition.publisher:
            return edition.publisher
    return None


def _imprint(item: Any, edition: Any | None) -> str | None:
    imprint = _organization_name(item, "imprint")
    if imprint is not None:
        return imprint
    return _optional_text(getattr(edition, "imprint", None))


def _organization_name(item: Any, role: str) -> str | None:
    rows = sorted(
        _loaded_rows(item, "organization_links"),
        key=lambda link: (
            str(getattr(link, "role", "") or "").casefold(),
            str(getattr(getattr(link, "organization", None), "name", "") or "").casefold(),
        ),
    )
    for link in rows:
        if getattr(link, "role", None) != role:
            continue
        organization = getattr(link, "organization", None)
        name = getattr(organization, "name", None)
        if name:
            return str(name)
    return None


def _apply_organization_overrides(base: dict[str, Any], item: Any) -> None:
    editions = base.get("editions")
    if not isinstance(editions, list):
        return
    publisher = _organization_name(item, "publisher")
    imprint = _organization_name(item, "imprint")
    for edition in editions:
        if not isinstance(edition, dict):
            continue
        if publisher is not None:
            edition["publisher"] = publisher
        if imprint is not None:
            edition["imprint"] = imprint


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
    item: Any, extra_provider_links: list[ExternalProviderIdResponse] | None = None
) -> list[ExternalProviderIdResponse]:
    links: list[ExternalProviderIdResponse] = []
    seen: dict[tuple[str, str, str], ExternalProviderIdResponse] = {}
    loaded_provider_links = item.__dict__.get("provider_links", []) if hasattr(item, "__dict__") else []
    for link in _provider_links_from_models(loaded_provider_links, entity_type="item"):
        _append_provider_link(
            links,
            seen,
            provider=link.provider.value,
            entity_type=link.entity_type,
            provider_item_id=link.provider_item_id,
            site_url=link.site_url,
            api_url=link.api_url,
        )
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


def _provider_links_from_models(
    rows: Any, *, entity_type: str
) -> list[ExternalProviderIdResponse]:
    links: list[ExternalProviderIdResponse] = []
    for row in rows or []:
        provider = getattr(row, "provider", None)
        provider_item_id = getattr(row, "provider_item_id", None)
        if provider is None or not provider_item_id:
            continue
        links.append(
            ExternalProviderIdResponse(
                provider=provider,
                entity_type=entity_type,
                provider_item_id=provider_item_id,
                site_url=getattr(row, "site_url", None),
                api_url=getattr(row, "api_url", None),
            )
        )
    return links


def _append_provider_link(
    links: list[ExternalProviderIdResponse],
    seen: dict[tuple[str, str, str], ExternalProviderIdResponse],
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
    link = ExternalProviderIdResponse(
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
