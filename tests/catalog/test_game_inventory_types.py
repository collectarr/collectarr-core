from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.catalog.catalog_item_schema import (
    catalog_item_payload_contract,
    validate_catalog_item_payload,
)
from app.catalog.kind_registry import catalog_kind_for
from app.models.base import ItemKind
from app.models.catalog_game_hardware_item import GameHardwareItem
from app.models.catalog_game_toy_item import GameToyItem
from app.schemas.catalog_game_hardware_item import CatalogGameHardwareItemResponse
from app.schemas.catalog_game_toy_item import CatalogGameToyItemResponse


def test_hardware_and_toys_own_separate_roots_and_strict_fields():
    hardware = catalog_kind_for(ItemKind.game_hardware)
    toy = catalog_kind_for(ItemKind.game_toy)
    assert hardware.model is GameHardwareItem
    assert toy.model is GameToyItem
    assert hardware.response_model is CatalogGameHardwareItemResponse
    assert toy.response_model is CatalogGameToyItemResponse
    assert hardware.document is not toy.document
    contracts = catalog_item_payload_contract()["kinds"]
    assert "hardware_type" in contracts["game_hardware"]["properties"]
    assert "toy_type" in contracts["game_toy"]["properties"]
    assert "hardware_type" not in contracts["game_toy"]["properties"]
    assert "toy_type" not in contracts["game"]["properties"]
    for kind, field in ((ItemKind.game_hardware, "toy_type"),
                        (ItemKind.game_hardware, "serial_number"),
                        (ItemKind.game_toy, "platform"),
                        (ItemKind.game_toy, "hardware_type"),
                        (ItemKind.game, "toy_type")):
        with pytest.raises(ValueError):
            validate_catalog_item_payload(kind, {"title": "Fixture", field: "wrong type"})


@pytest.mark.parametrize("model, foreign_field", [
    (CatalogGameHardwareItemResponse, "toy_type"),
    (CatalogGameHardwareItemResponse, "serial_number"),
    (CatalogGameToyItemResponse, "platform"),
])
def test_response_models_do_not_accept_other_inventory_or_personal_fields(model, foreign_field):
    with pytest.raises(ValidationError):
        model.model_validate({"id": uuid4(), "title": "Fixture", "revision": 1,
                              foreign_field: "unsupported"})


def test_hardware_and_toy_partial_dates_and_fields_round_trip():
    hardware = validate_catalog_item_payload(ItemKind.game_hardware, {
        "title": "Pocket Console", "platform": "Portable", "hardware_type": "Console",
        "release_date_parts": {"year": 2025}, "series_title": "Pocket",
    })
    assert hardware["hardware_type"] == "Console"
    assert hardware["release_date_parts"] == {"year": 2025}
    toy = validate_catalog_item_payload(ItemKind.game_toy, {
        "title": "Star Figure", "toy_type": "Amiibo", "toy_subtype": "Figure",
    })
    assert toy["toy_type"] == "Amiibo"
    assert toy["toy_subtype"] == "Figure"
