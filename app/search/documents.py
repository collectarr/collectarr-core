from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm.attributes import NO_VALUE

from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.models.canonical import Item


def item_search_document(item: Item) -> dict[str, Any]:
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
    platforms: list[str] = []
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
    bundle_titles: list[str] = []
    bundle_release_ids: list[str] = []
    series_title = item.volume.series.title if item.volume and item.volume.series else None
    volume_name = item.volume.name if item.volume else None
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
            edition.metadata_json,
            fallback_format=edition.format,
            kind=item.kind,
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
        normalized = _normalized_metadata(edition.metadata_json)
        catalog_number = catalog_number or _optional_text(getattr(edition, "catalog_number", None))
        release_status = release_status or _optional_text(getattr(edition, "release_status", None))
        language = language or _optional_text(getattr(edition, "language", None))
        imprint = imprint or _optional_text(getattr(edition, "imprint", None))
        subtitle = subtitle or _optional_text(getattr(edition, "subtitle", None))
        series_group = series_group or _optional_text(getattr(edition, "series_group", None))
        age_rating = age_rating or _optional_text(getattr(edition, "age_rating", None))
        platforms.extend(_string_list(normalized.get("platforms")))
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

    bundle_releases = _loaded_primary_bundle_releases(item)
    for bundle_release in bundle_releases:
        _append_unique(bundle_titles, bundle_release.title)
        _append_unique(bundle_release_ids, str(bundle_release.id))
        if bundle_release.barcode:
            _append_unique(barcodes, _normalized_barcode(bundle_release.barcode))
            barcode = barcode or _normalized_barcode(bundle_release.barcode)
        if bundle_release.sku:
            _append_unique(barcodes, _normalized_barcode(bundle_release.sku))
            barcode = barcode or _normalized_barcode(bundle_release.sku)

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
        "bundle_titles": bundle_titles,
        "bundle_release_ids": bundle_release_ids,
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


def _source_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    source = metadata.get("source")
    return source if isinstance(source, dict) else {}


def _normalized_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    normalized = metadata.get("normalized")
    return normalized if isinstance(normalized, dict) else {}


def _physical_format_label(
    metadata: dict[str, Any] | None,
    *,
    fallback_format: str | None,
    kind: Any,
) -> str | None:
    config = None
    if isinstance(metadata, dict):
        normalized = metadata.get("normalized")
        if isinstance(normalized, dict) and normalized.get("physical_format"):
            config = physical_format_for_id(str(normalized["physical_format"]))
    if config is None and fallback_format and is_video_item_kind(kind):
        config = physical_format_for_id(fallback_format)
    return config.label if config else None


def _organization_name(item: Item, role: str) -> str | None:
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


def _loaded_primary_bundle_releases(item: Item) -> list[Any]:
    bundle_attr = inspect(item).attrs.primary_bundle_releases.loaded_value
    if bundle_attr is NO_VALUE or bundle_attr is None:
        return []
    return list(bundle_attr)


def _loaded_rows(item: Item, attr_name: str) -> list[Any]:
    attr = inspect(item).attrs[attr_name].loaded_value
    if attr is NO_VALUE or attr is None:
        return []
    return list(attr)
