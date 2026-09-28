from __future__ import annotations

from typing import Any

from app.models.canonical_catalog_items import CanonicalCatalogItem


def catalog_item_search_document(item: CanonicalCatalogItem) -> dict[str, Any]:
    """Build a source-neutral search document from the v1 Catalog Item."""
    details = item.details if isinstance(item.details, dict) else {}
    identifiers = details.get("identifiers")
    identifiers = identifiers if isinstance(identifiers, list) else []
    identifier_values: list[str] = []
    barcodes: list[str] = []
    direct_barcode = _text(details.get("barcode"))
    if direct_barcode:
        barcodes.append(direct_barcode)
    for entry in identifiers:
        if not isinstance(entry, dict):
            continue
        value = _text(entry.get("value"))
        if value is None:
            continue
        identifier_values.append(value)
        if str(entry.get("identifier_type", "")).casefold() in {
            "barcode",
            "ean",
            "gtin",
            "upc",
        }:
            barcodes.append(value)
    barcodes = list(dict.fromkeys(barcodes))
    release_date = details.get("release_date") or details.get("publication_date")
    release_year = _year(release_date)
    publisher = _text(details.get("publisher")) or _first_named(
        details.get("publishers") or details.get("labels")
    )
    creators = _names(details.get("artists")) + _names(
        details.get("credits") or details.get("contributors") or details.get("creators")
    )
    search_values = [item.title, item.sort_title or "", *_flatten_text(details)]
    return {
        "id": str(item.id),
        "kind": item.kind,
        "title": item.title,
        "sort_title": item.sort_title,
        "search_text": " ".join(search_values).casefold(),
        "identifier_search": " ".join(
            [item.identifier_search, *identifier_values, *barcodes]
        ).casefold(),
        "barcode": direct_barcode or (barcodes[0] if barcodes else None),
        "barcodes": barcodes,
        "catalog_number": _text(details.get("catalog_number")),
        "release_date": _date_text(release_date),
        "release_year": release_year,
        "publisher": publisher,
        "creators": list(dict.fromkeys(creators)),
        "format": _text(details.get("format")),
        "country": _text(details.get("country")),
        "cover_image_url": _cover_url(details),
    }


def _text(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _year(value: object) -> int | None:
    if isinstance(value, dict):
        year = value.get("year")
        return year if isinstance(year, int) else None
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def _date_text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    year, month, day = (value.get(key) for key in ("year", "month", "day"))
    if not isinstance(year, int):
        return None
    result = f"{year:04d}"
    if isinstance(month, int):
        result += f"-{month:02d}"
        if isinstance(day, int):
            result += f"-{day:02d}"
    return result


def _first_named(value: object) -> str | None:
    if not isinstance(value, list):
        return _text(value)
    for entry in value:
        if isinstance(entry, dict):
            name = _text(entry.get("name"))
            if name:
                return name
        else:
            text = _text(entry)
            if text:
                return text
    return None


def _names(value: object) -> list[str]:
    if not isinstance(value, list):
        text = _text(value)
        return [text] if text else []
    names = []
    for entry in value:
        if isinstance(entry, dict):
            text = _text(entry.get("name") or entry.get("credited_name"))
        else:
            text = _text(entry)
        if text:
            names.append(text)
    return names


def _flatten_text(value: object) -> list[str]:
    if isinstance(value, dict):
        return [part for nested in value.values() for part in _flatten_text(nested)]
    if isinstance(value, list):
        return [part for nested in value for part in _flatten_text(nested)]
    text = _text(value)
    return [text] if text else []


def _cover_url(details: dict[str, Any]) -> str | None:
    direct = _text(details.get("cover_image_url"))
    if direct:
        return direct
    images = details.get("images")
    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict):
                url = _text(image.get("url"))
                if url:
                    return url
    return None
