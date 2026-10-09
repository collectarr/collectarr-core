from uuid import uuid4

import pytest

from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.catalog_music_item import MusicItem
from app.services.canonical_correction_targets import CanonicalCorrectionTargetService


def _music_item() -> MusicItem:
    return MusicItem(
        id=uuid4(),
        title="Deluxe Edition",
        artist_credits=[{"id": "artist-1", "name": "The Band", "sequence": 1}],
        genres=[],
        extra=[],
        credits=[],
        external_links=[],
        revision=1,
        discs=[
            {
                "id": str(uuid4()),
                "disc_number": 1,
                "sound_types": [],
                "recording_locations": [],
                "credits": [],
                "tracks": [],
            },
            {
                "id": str(uuid4()),
                "disc_number": 2,
                "sound_types": [],
                "recording_locations": [],
                "credits": [],
                "tracks": [],
            },
        ],
    )


def test_music_nested_lists_are_registered_as_correction_fields():
    fields = CanonicalCorrectionTargetService._field_specs(
        ItemKind.music, "catalog_music_item", "catalog_item", MusicItem
    )
    field_types = {field.key: field.value_type for field in fields}

    assert field_types["artist_credits"] == "object_list"
    assert field_types["credits"] == "object_list"
    assert field_types["discs"] == "object_list"


def test_music_correction_validation_preserves_nested_ids_and_order():
    item = _music_item()
    proposed_discs = [dict(disc) for disc in item.discs]
    proposed_discs[0]["title"] = "First Disc"

    validated = CanonicalCorrectionTargetService._validated_music_fields(
        item, {"discs": proposed_discs}
    )

    assert [disc["id"] for disc in validated["discs"]] == [disc["id"] for disc in item.discs]
    assert validated["discs"][0]["title"] == "First Disc"


def test_music_correction_validation_rejects_duplicate_nested_ids():
    item = _music_item()
    duplicate_discs = [dict(disc) for disc in item.discs]
    duplicate_discs[1]["id"] = duplicate_discs[0]["id"]

    with pytest.raises(ApiHTTPException) as error:
        CanonicalCorrectionTargetService._validated_music_fields(item, {"discs": duplicate_discs})

    assert error.value.code == "invalid_canonical_music_payload"
