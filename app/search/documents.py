from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm.attributes import NO_VALUE

from app.catalog.kind_registry import CATALOG_KINDS_BY_MODEL
from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.models import MusicItem
from app.models.base import ItemKind
from app.models.catalog_movie_item import MovieItem
from app.models.partial_date import PartialDateValue


def item_search_document(item: Any) -> dict[str, Any]:
    barcode = None
    cover_url = None
    thumbnail_url = None
    publisher = _organization_name(item, "publisher")
    release_date = None
    release_region = None
    release_year = None
    barcodes: list[str] = []
    creators: list[str] = []
    characters: list[str] = []
    story_arcs: list[str] = []
    platforms = _string_list(getattr(item, "platforms", []))
    catalog_number = None
    release_status = None
    language = None
    imprint = _organization_name(item, "imprint")
    subtitle = None
    series_group = None
    age_rating = None
    runtime_minutes = getattr(item, "runtime_minutes", None)
    variant = None
    variant_names: list[str] = []
    series_title = None
    volume = getattr(item, "__dict__", {}).get("volume")
    if volume is not None:
        series_title = getattr(volume, "name", None) or getattr(volume, "title", None)
    volume_name = getattr(volume, "name", None) if volume is not None else None
    creator_links = sorted(
        _loaded_rows(item, "creator_links"),
        key=lambda link: (
            getattr(link, "created_at", None) is None,
            getattr(link, "created_at", None),
            str(getattr(link, "id", "") or ""),
        ),
    )
    if creator_links:
        creators.extend(
            [
                link.person.name
                for link in creator_links
                if getattr(link, "person", None) is not None and getattr(link.person, "name", None)
            ]
        )
    character_links = sorted(
        _loaded_rows(item, "character_appearances"),
        key=lambda appearance: (
            str(getattr(appearance, "role", "") or "").casefold(),
            str(getattr(getattr(appearance, "character", None), "name", "") or "").casefold(),
        ),
    )
    if character_links:
        characters.extend(
            [
                appearance.character.name
                for appearance in character_links
                if getattr(appearance, "character", None) is not None
                and getattr(appearance.character, "name", None)
            ]
        )
    story_arc_links = sorted(
        _loaded_rows(item, "story_arc_items"),
        key=lambda link: (
            getattr(link, "ordinal", None) is None,
            getattr(link, "ordinal", None) or 0,
            str(getattr(getattr(link, "story_arc", None), "name", "") or "").casefold(),
        ),
    )
    if story_arc_links:
        story_arcs.extend(
            [
                link.story_arc.name
                for link in story_arc_links
                if getattr(link, "story_arc", None) is not None
                and getattr(link.story_arc, "name", None)
            ]
        )

    for edition in item.editions:
        publisher = publisher or edition.publisher
        physical_format = _physical_format_label(
            fallback_format=edition.format,
            kind=item.kind,
            preferred=getattr(edition, "physical_format", None),
        )
        if physical_format:
            _append_unique(variant_names, physical_format)
            variant = variant or physical_format
        if edition.release_date and release_year is None:
            release_date = edition.release_date.isoformat()
            release_year = edition.release_date.year
        if edition.upc:
            _append_unique(barcodes, _normalized_barcode(edition.upc))
            barcode = barcode or _normalized_barcode(edition.upc)
        if edition.isbn:
            _append_unique(barcodes, _normalized_barcode(edition.isbn))
            barcode = barcode or _normalized_barcode(edition.isbn)
        catalog_number = catalog_number or _optional_text(getattr(edition, "catalog_number", None))
        release_status = release_status or _optional_text(getattr(edition, "release_status", None))
        language = language or _optional_text(getattr(edition, "language", None))
        imprint = imprint or _optional_text(getattr(edition, "imprint", None))
        subtitle = subtitle or _optional_text(getattr(edition, "subtitle", None))
        series_group = series_group or _optional_text(getattr(edition, "series_group", None))
        age_rating = age_rating or _optional_text(getattr(edition, "age_rating", None))
        primary = next((row for row in edition.variants if row.is_primary), None)
        for variant_row in edition.variants:
            _append_unique(variant_names, variant_row.name)
            if variant_row.barcode:
                _append_unique(barcodes, _normalized_barcode(variant_row.barcode))
                barcode = barcode or _normalized_barcode(variant_row.barcode)
            if variant_row.isbn:
                _append_unique(barcodes, _normalized_barcode(variant_row.isbn))
                barcode = barcode or _normalized_barcode(variant_row.isbn)
        if primary:
            variant = physical_format or primary.name
            cover_url = cover_url or primary.cover_image_url
            thumbnail_url = thumbnail_url or primary.thumbnail_image_url
        release_region = release_region or edition.region

    return {
        "id": str(item.id),
        "kind": item.kind.value,
        "title": item.title,
        "item_number": item.item_number,
        "runtime_minutes": runtime_minutes,
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
        "publisher": publisher,
        "release_date": release_date,
        "region": release_region,
        "release_year": release_year,
        "barcode": barcode,
        "barcodes": barcodes,
        "variant": variant,
        "variant_names": variant_names,
        "series_title": series_title,
        "volume_name": volume_name,
        "catalog_number": catalog_number,
        "creators": _unique(creators),
        "characters": _unique(characters),
        "story_arcs": _unique(story_arcs),
        "platforms": _unique(platforms),
        "release_status": release_status,
        "language": language,
        "imprint": imprint,
        "subtitle": subtitle,
        "series_group": series_group,
        "age_rating": age_rating,
    }


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
    recording_dates = [
        PartialDateValue.model_validate(disc["recording_date"])
        for disc in discs
        if disc.get("recording_date")
    ]
    release_date_parts = PartialDateValue.model_validate(date_value) if date_value else None
    if release_date_parts is None and recording_dates:
        release_date_parts = min(
            recording_dates,
            key=lambda value: (value.year or 9999, value.month or 1, value.day or 1),
        )
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


def _physical_format_label(
    *,
    fallback_format: str | None,
    kind: Any,
    preferred: str | None = None,
) -> str | None:
    config = physical_format_for_id(preferred) if preferred else None
    if config is None and fallback_format and is_video_item_kind(kind):
        config = physical_format_for_id(fallback_format)
    return config.label if config else None


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


def _loaded_rows(item: Any, attr_name: str) -> list[Any]:
    attr = inspect(item).attrs[attr_name].loaded_value
    if attr is NO_VALUE or attr is None:
        return []
    return list(attr)
