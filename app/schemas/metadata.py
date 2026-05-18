from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.models.base import ExternalProvider, ItemKind


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


class ReleaseResponse(BaseModel):
    id: UUID
    region: str
    release_date: date | None
    publisher: str | None
    external_ids: dict[str, Any] | None
    metadata_json: dict[str, Any] | None

    model_config = {"from_attributes": True}


class MetadataCredit(BaseModel):
    name: str
    role: str | None = None
    api_detail_url: str | None = None
    site_detail_url: str | None = None


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
    releases: list[ReleaseResponse] = []

    model_config = {"from_attributes": True}


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
    creators: list[MetadataCredit] = []
    characters: list[MetadataCredit] = []
    story_arcs: list[MetadataCredit] = []
    provider_links: list[ProviderLink] = []
    editions: list[EditionResponse] = []

    model_config = {"from_attributes": True}


class SearchResult(BaseModel):
    id: UUID
    kind: ItemKind
    title: str
    item_number: str | None = None
    synopsis: str | None = None
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


class MetadataProposalResponse(BaseModel):
    id: UUID
    provider: ExternalProvider
    provider_item_id: str | None
    query: str
    title: str | None
    status: str

    model_config = {"from_attributes": True}


def item_response_from_model(item: Any) -> ItemResponse:
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
            "creators": _credits(source.get("person_credits"))
            or _credits(normalized.get("creators")),
            "characters": _credits(source.get("character_credits"))
            or _credits(normalized.get("characters")),
            "story_arcs": _credits(source.get("story_arc_credits"))
            or _credits(normalized.get("story_arcs")),
            "provider_links": _provider_links(item),
        }
    )
    return ItemResponse(**base)


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
        for release in getattr(edition, "releases", []) or []:
            if release.publisher:
                return release.publisher
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
            )
        )
    return credits


def _provider_links(item: Any) -> list[ProviderLink]:
    links: list[ProviderLink] = []
    seen: set[tuple[str, str, str]] = set()
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
        for release in getattr(edition, "releases", []) or []:
            external_ids = getattr(release, "external_ids", None) or {}
            if not isinstance(external_ids, dict):
                continue
            for release_provider, release_id in external_ids.items():
                if release_id:
                    _append_provider_link(
                        links,
                        seen,
                        provider=str(release_provider),
                        entity_type="release",
                        provider_item_id=str(release_id),
                    )
    return links


def _append_provider_link(
    links: list[ProviderLink],
    seen: set[tuple[str, str, str]],
    *,
    provider: str,
    entity_type: str,
    provider_item_id: str,
    site_url: str | None = None,
    api_url: str | None = None,
) -> None:
    key = (provider, entity_type, provider_item_id)
    if key in seen:
        return
    try:
        provider_enum = ExternalProvider(provider)
    except ValueError:
        return
    seen.add(key)
    links.append(
        ProviderLink(
            provider=provider_enum,
            entity_type=entity_type,
            provider_item_id=provider_item_id,
            site_url=site_url,
            api_url=api_url,
        )
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
