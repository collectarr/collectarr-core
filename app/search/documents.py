from typing import Any

from app.models.canonical import Item


def item_search_document(item: Item) -> dict[str, Any]:
    barcode = None
    cover_url = None
    thumbnail_url = None
    publisher = None
    release_date = None
    release_region = None
    release_year = None
    barcodes: list[str] = []
    creators: list[str] = []
    characters: list[str] = []
    story_arcs: list[str] = []
    variant = None
    variant_names: list[str] = []
    series_title = item.volume.series.title if item.volume and item.volume.series else None
    volume_name = item.volume.name if item.volume else None

    for edition in item.editions:
        publisher = publisher or edition.publisher
        if edition.release_date and release_year is None:
            release_date = edition.release_date.isoformat()
            release_year = edition.release_date.year
        if edition.upc:
            _append_unique(barcodes, _normalized_barcode(edition.upc))
            barcode = barcode or _normalized_barcode(edition.upc)
        if edition.isbn:
            _append_unique(barcodes, _normalized_barcode(edition.isbn))
            barcode = barcode or _normalized_barcode(edition.isbn)
        source = _source_metadata(edition.metadata_json)
        creators.extend(_credit_names(source.get("person_credits")))
        characters.extend(_credit_names(source.get("character_credits")))
        story_arcs.extend(_credit_names(source.get("story_arc_credits")))
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
            variant = primary.name
            cover_url = cover_url or primary.cover_image_url
            thumbnail_url = thumbnail_url or primary.thumbnail_image_url
        for release in edition.releases:
            release_region = release_region or release.region

    return {
        "id": str(item.id),
        "kind": item.kind.value,
        "title": item.title,
        "item_number": item.item_number,
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
        "creators": _unique(creators),
        "characters": _unique(characters),
        "story_arcs": _unique(story_arcs),
    }


def _source_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    source = metadata.get("source")
    return source if isinstance(source, dict) else {}


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
