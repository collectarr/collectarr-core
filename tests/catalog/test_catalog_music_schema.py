"""Tests for Music catalog response schemas and strict validation."""

from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.schemas.catalog_music_item import (
    CatalogMusicDiscResponse,
    CatalogMusicItemResponse,
    CatalogMusicTrackResponse,
    MusicDiscFormatFamily,
    validate_music_discs,
)


def test_catalog_music_disc_validation_success():
    disc = CatalogMusicDiscResponse(
        id=uuid4(),
        disc_number=1,
        title="Side 1",
        format_family=MusicDiscFormatFamily.vinyl,
        format='Vinyl (12" LP)',
        sound_types=["stereo"],
        color="Black",
        vinyl_weight_grams=180,
        rpm="33⅓",
        matrix_number=None,
        matrix_number_side_a="MTRX-A",
        matrix_number_side_b="MTRX-B",
        tracks=[
            CatalogMusicTrackResponse(
                id=uuid4(),
                position="A1",
                position_order=0,
                title="First Song",
            )
        ],
    )
    assert disc.disc_number == 1
    assert disc.format_family == MusicDiscFormatFamily.vinyl
    assert disc.vinyl_weight_grams == 180
    assert disc.rpm == "33⅓"
    assert disc.color == "Black"


def test_catalog_music_disc_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        CatalogMusicDiscResponse.model_validate(
            {
                "id": str(uuid4()),
                "disc_number": 1,
                "unexpected_field": "disallowed",
                "tracks": [],
            }
        )


def test_catalog_music_item_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        CatalogMusicItemResponse.model_validate(
            {
                "id": str(uuid4()),
                "title": "Album",
                "format": "Vinyl",  # format at album level is forbidden
                "artist_credits": [],
                "genres": [],
                "studios": [],
                "composers": [],
                "conductors": [],
                "choruses": [],
                "compositions": [],
                "orchestras": [],
                "songwriters": [],
                "producers": [],
                "engineers": [],
                "musicians": [],
                "external_links": [],
                "revision": 1,
                "discs": [],
            }
        )


def test_disc_semantics_vinyl_weight_only_for_vinyl():
    with pytest.raises(
        ValueError, match="vinyl_weight_grams is only allowed when format_family is vinyl"
    ):
        CatalogMusicDiscResponse(
            id=uuid4(),
            disc_number=1,
            format_family=MusicDiscFormatFamily.cd,
            vinyl_weight_grams=180,
            tracks=[],
        )


def test_disc_semantics_rpm_only_for_rotating_media():
    with pytest.raises(ValueError, match="RPM is not allowed for cd discs"):
        CatalogMusicDiscResponse(
            id=uuid4(),
            disc_number=1,
            format_family=MusicDiscFormatFamily.cd,
            rpm="33",
            tracks=[],
        )


def test_disc_semantics_side_matrix_not_allowed_for_digital():
    with pytest.raises(ValueError, match="Side matrix numbers are not allowed for cd discs"):
        CatalogMusicDiscResponse(
            id=uuid4(),
            disc_number=1,
            format_family=MusicDiscFormatFamily.cd,
            matrix_number_side_a="CD-SIDE-A",
            tracks=[],
        )


def test_disc_semantics_optical_allows_matrix_number():
    disc = CatalogMusicDiscResponse(
        id=uuid4(),
        disc_number=1,
        format_family=MusicDiscFormatFamily.cd,
        matrix_number="CD-RUNOUT-1234",
        tracks=[],
    )
    assert disc.matrix_number == "CD-RUNOUT-1234"


def test_validate_music_discs_preserves_ids_and_orders():
    disc_id = uuid4()
    track_id = uuid4()
    raw = [
        {
            "id": disc_id,
            "disc_number": 1,
            "format_family": "cd",
            "format": "CD",
            "tracks": [
                {
                    "id": track_id,
                    "position": "1",
                    "position_order": 0,
                    "title": "Track 1",
                }
            ],
        }
    ]
    normalized = validate_music_discs(raw)
    assert len(normalized) == 1
    assert normalized[0]["id"] == str(disc_id)
    assert normalized[0]["format_family"] == "cd"
    assert normalized[0]["tracks"][0]["id"] == str(track_id)
