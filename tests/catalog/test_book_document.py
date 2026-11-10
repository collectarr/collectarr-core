from uuid import uuid4

import pytest

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.models.base import ItemKind
from app.schemas.catalog_book_item import CatalogBookItemResponse


def test_book_edition_details_round_trip_through_the_public_response():
    payload = {
        "title": "Fictional Book",
        "box_set": "Fictional Collection",
        "publication_place": "Bucharest",
        "printed_by": "Fictional Printer",
        "paper_type": "Acid-free",
        "printing_number": 2,
        "extras": ["Map", "Ribbon"],
        "number_line": "10 9 8 7 6 5 4 3 2",
        "width_mm": 133,
        "height_mm": 197,
        "spine_thickness_mm": 19,
        "weight_grams": 213,
        "original_subtitle": "Original subtitle",
        "original_country": "Romania",
        "original_publisher": "Fictional Publisher",
        "original_publication_place": "Bucharest",
        "audio_abridged": True,
    }
    validated = validate_catalog_item_payload(ItemKind.book, payload)
    response = CatalogBookItemResponse(id=uuid4(), kind="book", revision=1, **validated)
    assert {key: response.model_dump()[key] for key in payload} == payload


@pytest.mark.parametrize("field", ["width_mm", "weight_grams", "printing_number"])
def test_book_measurements_require_integers(field):
    with pytest.raises(ValueError):
        validate_catalog_item_payload(ItemKind.book, {"title": "Book", field: "invalid"})


@pytest.mark.parametrize("field", ["width_mm", "height_mm", "spine_thickness_mm", "weight_grams", "printing_number"])
def test_book_measurements_reject_negative_values(field):
    with pytest.raises(ValueError, match="must not be negative"):
        validate_catalog_item_payload(ItemKind.book, {"title": "Book", field: -1})
