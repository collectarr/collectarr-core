"""Every contained-object list in the Catalog Item contract carries a display title."""

from collections.abc import Iterator
from typing import Any

from app.catalog.catalog_item_schema import catalog_item_payload_contract


def _variants(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return [*schema.get("anyOf", []), schema]


def _object_lists(properties: dict[str, Any], path: str) -> Iterator[tuple[str, dict[str, Any]]]:
    for key, schema in properties.items():
        field_path = f"{path}{key}"
        for variant in _variants(schema):
            items = variant.get("items") if variant.get("type") == "array" else None
            if not items:
                continue
            for item in _variants(items):
                if item.get("type") == "object" and "properties" in item:
                    yield field_path, schema
                    yield from _object_lists(item["properties"], f"{field_path}.")
                    break


def test_every_object_list_has_a_title():
    for kind, kind_schema in catalog_item_payload_contract()["kinds"].items():
        untitled = [
            path
            for path, schema in _object_lists(kind_schema["properties"], "")
            if not schema.get("title")
        ]
        assert untitled == [], f"{kind} lists without a title: {untitled}"


def test_music_titles_name_the_disc_and_track_lists():
    properties = catalog_item_payload_contract()["kinds"]["music"]["properties"]
    disc = next(
        variant["items"]
        for variant in properties["discs"]["anyOf"]
        if variant.get("type") == "array"
    )

    assert properties["discs"]["title"] == "Discs"
    assert properties["credits"]["title"] == "Credits"
    assert properties["external_links"]["title"] == "External links"
    assert disc["properties"]["tracks"]["title"] == "Tracks"
    assert disc["properties"]["credits"]["title"] == "Credits"
    assert properties["barcode"]["title"] == "Barcode"
