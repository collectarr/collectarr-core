from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.providers.base import NormalizedItem
from app.schemas.admin import ProviderFieldStateResponse


def _present(value: Any) -> bool:
    return value is not None and value != [] and value != {}


def _state(key: str, value: Any, *, import_only: bool = False) -> ProviderFieldStateResponse:
    if import_only:
        return ProviderFieldStateResponse(key=key, state="import_only", value=value)
    if _present(value):
        return ProviderFieldStateResponse(key=key, state="present", value=value)
    return ProviderFieldStateResponse(key=key, state="missing_from_provider")


def provider_preview_field_states(
    normalized: NormalizedItem,
    *,
    physical_format_id: str | None,
    physical_format_label: str | None,
) -> list[ProviderFieldStateResponse]:
    values: Mapping[str, Any] = {
        "title": normalized.title,
        "item_number": normalized.item_number,
        "synopsis": normalized.synopsis,
        "series_title": normalized.series_title,
        "volume_name": normalized.volume_name,
        "volume_number": normalized.volume_number,
        "volume_start_year": normalized.volume_start_year,
        "publisher": normalized.publisher,
        "imprint": normalized.imprint,
        "edition_title": normalized.edition_title,
        "edition_format": normalized.edition_format,
        "physical_format": physical_format_id,
        "physical_format_label": physical_format_label,
        "release_date": normalized.release_date,
        "barcode": normalized.barcode,
        "isbn": normalized.isbn,
        "variant_name": normalized.variant_name,
        "cover_image_url": normalized.cover_image_url,
        "cover_price_cents": normalized.cover_price_cents,
        "currency": normalized.currency,
        "country": normalized.country,
        "language": normalized.language,
        "age_rating": normalized.age_rating,
        "audience_rating": normalized.audience_rating,
        "subtitle": normalized.subtitle,
        "series_group": normalized.series_group,
        "page_count": normalized.page_count,
        "runtime_minutes": normalized.runtime_minutes,
        "track_count": normalized.track_count,
        "catalog_number": normalized.catalog_number,
        "creators": [credit.name for credit in normalized.creators],
        "characters": [credit.name for credit in normalized.characters],
        "story_arcs": [credit.name for credit in normalized.story_arcs],
        "platforms": normalized.platforms,
        "genres": normalized.genres,
        "release_status": normalized.release_status,
        "tracks": normalized.tracks,
    }
    return [
        _state("title", values["title"]),
        _state("item_number", values["item_number"]),
        _state("synopsis", values["synopsis"]),
        _state("series_title", values["series_title"]),
        _state("volume_name", values["volume_name"]),
        _state("volume_number", values["volume_number"]),
        _state("volume_start_year", values["volume_start_year"]),
        _state("publisher", values["publisher"]),
        _state("imprint", values["imprint"]),
        _state("edition_title", values["edition_title"]),
        _state("edition_format", values["edition_format"]),
        _state("physical_format", values["physical_format"], import_only=physical_format_id is None),
        _state(
            "physical_format_label",
            values["physical_format_label"],
            import_only=physical_format_label is None,
        ),
        _state("release_date", values["release_date"]),
        _state("barcode", values["barcode"]),
        _state("isbn", values["isbn"]),
        _state("variant_name", values["variant_name"]),
        _state("cover_image_url", values["cover_image_url"]),
        _state("cover_price_cents", values["cover_price_cents"]),
        _state("currency", values["currency"]),
        _state("country", values["country"]),
        _state("language", values["language"]),
        _state("age_rating", values["age_rating"]),
        _state("audience_rating", values["audience_rating"]),
        _state("subtitle", values["subtitle"]),
        _state("series_group", values["series_group"]),
        _state("page_count", values["page_count"]),
        _state("runtime_minutes", values["runtime_minutes"]),
        _state("track_count", values["track_count"]),
        _state("catalog_number", values["catalog_number"]),
        _state("creators", values["creators"]),
        _state("characters", values["characters"]),
        _state("story_arcs", values["story_arcs"]),
        _state("platforms", values["platforms"]),
        _state("genres", values["genres"]),
        _state("release_status", values["release_status"]),
        _state("tracks", values["tracks"]),
    ]
