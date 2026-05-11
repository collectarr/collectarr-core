from typing import Any

from app.models.canonical import Item


def item_search_document(item: Item) -> dict[str, Any]:
    cover_url = None
    publisher = None
    release_region = None
    series_title = item.volume.series.title if item.volume and item.volume.series else None
    volume_name = item.volume.name if item.volume else None

    for edition in item.editions:
        publisher = publisher or edition.publisher
        primary = next((variant for variant in edition.variants if variant.is_primary), None)
        if primary:
            cover_url = primary.cover_image_url
        for release in edition.releases:
            release_region = release_region or release.region

    return {
        "id": str(item.id),
        "kind": item.kind.value,
        "title": item.title,
        "item_number": item.item_number,
        "synopsis": item.synopsis,
        "cover_image_url": cover_url,
        "publisher": publisher,
        "region": release_region,
        "series_title": series_title,
        "volume_name": volume_name,
    }
