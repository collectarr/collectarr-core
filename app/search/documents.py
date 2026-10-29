from typing import Any

from app.catalog.kind_registry import CATALOG_KINDS_BY_MODEL
from app.models import MusicItem
from app.models.base import ItemKind
from app.models.catalog_movie_item import MovieItem
from app.models.partial_date import PartialDateValue


def movie_item_search_document(item: MovieItem) -> dict[str, Any]:
    details = dict(item.details or {})
    date_value = details.get("release_date_parts") or details.get("release_date")
    try:
        release_date_parts = PartialDateValue.model_validate(date_value)
    except TypeError, ValueError:
        release_date_parts = None
    release_date = release_date_parts.iso_string if release_date_parts else None

    creators = _unique(
        _catalog_names(details.get("creators")) + _catalog_names(details.get("contributors"))
    )
    characters = _catalog_names(details.get("characters"))
    physical_format = _optional_text(details.get("physical_format"))
    variant = physical_format or _optional_text(details.get("variant_name"))

    return {
        "id": str(item.id),
        "kind": ItemKind.movie.value,
        "title": item.title,
        "item_number": _optional_text(details.get("item_number")),
        "runtime_minutes": details.get("runtime_minutes"),
        "cover_image_url": _optional_text(details.get("cover_image_url")),
        "thumbnail_image_url": _optional_text(details.get("thumbnail_image_url")),
        "publisher": _optional_text(details.get("publisher")),
        "release_date": release_date,
        "region": _optional_text(details.get("country")),
        "release_year": release_date_parts.year if release_date_parts else None,
        "barcode": _optional_text(item.barcode),
        "barcodes": [item.barcode] if item.barcode else [],
        "variant": variant,
        "variant_names": [variant] if variant else [],
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": _optional_text(details.get("series_title")),
        "volume_name": _optional_text(details.get("volume_name")),
        "catalog_number": _optional_text(item.catalog_number),
        "creators": creators,
        "characters": characters,
        "story_arcs": _string_list(details.get("story_arcs")),
        "platforms": [],
        "release_status": _optional_text(details.get("release_status")),
        "language": _optional_text(details.get("language")),
        "imprint": _optional_text(details.get("imprint")),
        "subtitle": _optional_text(details.get("subtitle")),
        "series_group": _optional_text(details.get("series_group")),
        "age_rating": _optional_text(details.get("age_rating")),
    }


def music_item_search_document(item: MusicItem) -> dict[str, Any]:
    discs = list(item.discs or [])
    date_value = item.release_date or item.original_release_date
    release_date_parts = PartialDateValue.model_validate(date_value) if date_value else None
    release_date = release_date_parts.iso_string if release_date_parts else None
    formats = _unique([_optional_text(disc.get("format")) for disc in discs])
    contributors = [item.artist] if item.artist else []
    contributors.extend(
        credit.get("name")
        for credit in item.artist_credits or []
        if credit.get("name")
    )
    contributors.extend(
        credit.get("name")
        for credit in item.credits or []
        if credit.get("name")
    )
    contributors.extend(
        credit.get("name")
        for disc in discs
        for credit in disc.get("credits", [])
        if credit.get("name")
    )
    return {
        "id": str(item.id),
        "kind": ItemKind.music.value,
        "title": item.title,
        "item_number": None,
        "runtime_minutes": None,
        "cover_image_url": item.cover_image_url,
        "thumbnail_image_url": item.thumbnail_image_url or item.cover_image_url,
        "publisher": item.label,
        "release_date": release_date,
        "region": item.country,
        "release_year": release_date_parts.year if release_date_parts else None,
        "barcode": item.barcode,
        "barcodes": [item.barcode] if item.barcode else [],
        "variant": formats[0] if formats else None,
        "variant_names": formats,
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": item.artist,
        "volume_name": None,
        "catalog_number": item.catalog_number,
        "creators": _unique(contributors),
        "characters": [],
        "story_arcs": [],
        "platforms": [],
        "release_status": None,
        "language": None,
        "imprint": None,
        "subtitle": item.subtitle,
        "series_group": None,
        "age_rating": None,
    }


def catalog_search_document(entity: Any) -> dict[str, Any]:
    definition = CATALOG_KINDS_BY_MODEL.get(type(entity))
    if definition is None:
        raise TypeError(f"Unsupported catalog entity type: {type(entity)!r}")
    return definition.search_document(entity)


def flat_catalog_item_search_document(item: Any, kind: ItemKind) -> dict[str, Any]:
    """Project a flat typed Catalog Item root into the shared search shape."""
    details = dict(getattr(item, "details", {}) or {})
    date_value = details.get("release_date_parts") or details.get("release_date")
    try:
        release_date_parts = PartialDateValue.model_validate(date_value)
    except TypeError, ValueError:
        release_date_parts = None
    release_date = release_date_parts.iso_string if release_date_parts else None

    creators = _catalog_names(details.get("creators"))
    for values in (
        details.get("contributors"),
        details.get("artist_credits"),
        details.get("credits"),
    ):
        creators.extend(_catalog_names(values))
    creators = _unique(creators)
    barcode = _normalized_barcode(_optional_text(getattr(item, "barcode", None)))
    barcodes = [barcode] if barcode else []
    for identifier in details.get("identifiers", []):
        raw_value = identifier.get("value") if isinstance(identifier, dict) else identifier
        value = _normalized_barcode(_optional_text(raw_value))
        _append_unique(barcodes, value)
    barcode = barcode or (barcodes[0] if barcodes else None)

    physical_format = _optional_text(details.get("physical_format"))
    variant = physical_format or _optional_text(details.get("format"))
    if variant is None:
        variant = _optional_text(details.get("edition_title"))
    return {
        "id": str(item.id),
        "kind": kind.value,
        "title": getattr(item, "title", None),
        "primary_label": getattr(item, "title", None) or getattr(item, "sort_key", None) or str(item.id),
        "item_number": _optional_text(details.get("item_number") or details.get("issue_number")),
        "runtime_minutes": details.get("runtime_minutes"),
        "cover_image_url": _optional_text(details.get("cover_image_url")),
        "thumbnail_image_url": _optional_text(details.get("thumbnail_image_url")),
        "publisher": _optional_text(details.get("publisher") or details.get("label")),
        "release_date": release_date,
        "region": _optional_text(
            details.get("country") or details.get("release_region") or details.get("region")
        ),
        "release_year": release_date_parts.year if release_date_parts else None,
        "barcode": barcode,
        "barcodes": barcodes,
        "variant": variant,
        "variant_names": [variant] if variant else [],
        "bundle_titles": [],
        "bundle_release_ids": [],
        "series_title": _optional_text(details.get("series_title")),
        "volume_name": _optional_text(details.get("volume_name")),
        "catalog_number": _optional_text(
            getattr(item, "catalog_number", None) or details.get("catalog_number")
        ),
        "creators": creators,
        "characters": _catalog_names(details.get("characters")),
        "story_arcs": _catalog_names(details.get("story_arcs")),
        "platforms": _catalog_names(details.get("platforms")),
        "release_status": _optional_text(details.get("release_status")),
        "language": _optional_text(details.get("language")),
        "imprint": _optional_text(details.get("imprint")),
        "subtitle": _optional_text(details.get("subtitle")),
        "series_group": _optional_text(details.get("series_group")),
        "age_rating": _optional_text(details.get("age_rating")),
    }


def _credit_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        name = value.get("name")
        if name:
            names.append(str(name))
    return names


def _catalog_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        if isinstance(value, str):
            name = value.strip()
        elif isinstance(value, dict):
            name = str(value.get("name") or "").strip()
        else:
            name = ""
        if name:
            _append_unique(names, name)
    return names


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text:
            names.append(text)
    return names


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _append_unique(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


def _normalized_barcode(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().replace("-", "").replace(" ", "")
    return normalized or None


def _unique(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    for value in values:
        _append_unique(unique_values, value)
    return unique_values
