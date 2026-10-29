import pytest

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.models.base import ItemKind


def test_comic_publication_fields_and_partial_dates_are_not_conflated():
    payload = {
        "title": "Issue title", "subtitle": "Issue subtitle",
        "series_title": "Series", "issue_number": "1/2",
        "variant": "B", "variant_description": "Foil cover",
        "publication_age": "Modern", "age_rating": "Teen",
        "cover_date": {"year": 2024},
        "release_date_parts": {"month": 5, "day": 3},
    }
    projected = validate_catalog_item_payload(ItemKind.comic, payload)
    for field, value in payload.items():
        assert projected[field] == value


def test_comic_publication_age_rejects_non_text_values():
    with pytest.raises(ValueError, match="publication_age"):
        validate_catalog_item_payload(ItemKind.comic, {
            "title": "Issue", "publication_age": 2024,
        })


def test_comic_credits_and_appearances_use_one_list_each():
    payload = {
        "title": "Issue",
        "creators": [{"name": "Writer", "role": "Writer", "person_id": "p1"}],
        "characters": ["Sidekick", {"name": "Hero", "character_id": "c1"}],
        "contributors": [{"name": "Writer", "role": "Writer"}],
        "character_details": [{"name": "Hero"}],
    }
    projected = validate_catalog_item_payload(ItemKind.comic, payload)
    assert projected["creators"] == payload["creators"]
    assert projected["characters"] == payload["characters"]
    assert "contributors" not in projected
    assert "character_details" not in projected
