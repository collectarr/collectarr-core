from typing import Any

from app.models.canonical import Item


def item_search_document(item: Item) -> dict[str, Any]:
    cover_url = None
    thumbnail_url = None
    publisher = None
    release_region = None
    release_year = None
    barcodes: list[str] = []
    series_title = item.volume.series.title if item.volume and item.volume.series else None
    volume_name = item.volume.name if item.volume else None

    for edition in item.editions:
        publisher = publisher or edition.publisher
        if edition.release_date and release_year is None:
            release_year = edition.release_date.year
        if edition.upc:
            barcodes.append(edition.upc)
        if edition.isbn:
            barcodes.append(edition.isbn)
        primary = next((variant for variant in edition.variants if variant.is_primary), None)
        for variant in edition.variants:
            if variant.barcode:
                barcodes.append(variant.barcode)
            if variant.isbn:
                barcodes.append(variant.isbn)
        if primary:
            cover_url = primary.cover_image_url
            thumbnail_url = primary.thumbnail_image_url
        for release in edition.releases:
            release_region = release_region or release.region

    return {
        "id": str(item.id),
        "kind": item.kind.value,
        "title": item.title,
        "item_number": item.item_number,
        "synopsis": item.synopsis,
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
        "publisher": publisher,
        "region": release_region,
        "release_year": release_year,
        "barcodes": barcodes,
        "series_title": series_title,
        "volume_name": volume_name,
    }
