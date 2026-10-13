"""Tests for the strict Music v2 catalog response and write schemas."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.models.base import ItemKind
from app.schemas.catalog_music_item import (
    CatalogMusicDiscResponse,
    CatalogMusicItemResponse,
    CatalogMusicTrackResponse,
    MusicDiscFormatFamily,
    validate_music_discs,
)


def _credit(*, role: str, name: str, sequence: int = 1, **extra: object) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "name": name,
        "role": role,
        "instruments": [],
        "sequence": sequence,
        **extra,
    }


def _disc(*, number: int = 1, **values: object) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "disc_number": number,
        "sound_types": [],
        "recording_locations": [],
        "credits": [],
        "tracks": [],
        **values,
    }


def _music_item(**values: object) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "kind": "music",
        "title": "Album",
        "revision": 1,
        "artist_credits": [],
        "credits": [],
        "genres": [],
        "extra": [],
        "external_links": [],
        "discs": [],
        **values,
    }


def _proposal(*, discs: list[dict[str, object]] | None = None, **values: object) -> dict[str, object]:
    return {
        "title": "Album",
        "artist_credits": [],
        "credits": [],
        "genres": [],
        "extra": [],
        "external_links": [],
        "discs": discs if discs is not None else [_disc()],
        **values,
    }


def test_music_disc_accepts_coarse_family_and_disc_scoped_recording_data():
    raw = _disc(
        format_family="vinyl",
        format='12" Vinyl',
        recording_date={"year": 2025},
        recording_locations=["Abbey Road"],
        is_live=False,
        spars_code="DDD",
        color="Red",
        vinyl_weight_grams=180,
        rpm="45",
    )

    disc = CatalogMusicDiscResponse.model_validate(raw)

    assert disc.format_family == MusicDiscFormatFamily.vinyl
    assert disc.recording_date is not None and disc.recording_date.year == 2025
    assert disc.recording_locations == ["Abbey Road"]
    assert disc.spars_code == "DDD"


def test_catalog_music_disc_rejects_unknown_fields():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CatalogMusicDiscResponse.model_validate(_disc(unexpected_field="disallowed"))


def test_catalog_music_disc_requires_family_for_a_canonical_format():
    with pytest.raises(ValidationError, match="format requires an explicit format_family"):
        CatalogMusicDiscResponse.model_validate(_disc(format="custom silver disc"))


def test_catalog_music_disc_accepts_custom_format_with_explicit_family():
    disc = CatalogMusicDiscResponse.model_validate(
        _disc(format="custom silver disc", format_family="other")
    )
    assert disc.format == "custom silver disc"
    assert disc.format_family == MusicDiscFormatFamily.other


def test_catalog_music_disc_json_schema_requires_family_for_non_null_format():
    schema = CatalogMusicDiscResponse.model_json_schema()
    condition = schema["allOf"][0]

    assert condition["if"] == {
        "properties": {"format": {"type": "string"}},
        "required": ["format"],
    }
    assert condition["then"]["required"] == ["format_family"]
    assert condition["then"]["properties"]["format_family"] == {
        "not": {"type": "null"}
    }


def test_disc_vinyl_weight_is_limited_to_vinyl():
    with pytest.raises(ValidationError, match="vinyl_weight_grams is only allowed"):
        CatalogMusicDiscResponse.model_validate(
            _disc(format_family="opticalDisc", vinyl_weight_grams=180)
        )


def test_disc_rpm_is_limited_to_rotating_media():
    with pytest.raises(ValidationError, match="RPM is not allowed for opticalDisc discs"):
        CatalogMusicDiscResponse.model_validate(_disc(format_family="opticalDisc", rpm="33"))


def test_disc_side_matrices_are_rejected_for_optical_and_digital_families():
    with pytest.raises(ValidationError, match="Side matrix numbers are not allowed"):
        CatalogMusicDiscResponse.model_validate(
            _disc(format_family="opticalDisc", matrix_number_side_a="CD-SIDE-A")
        )


def test_optical_disc_accepts_generic_matrix_number():
    disc = CatalogMusicDiscResponse.model_validate(
        _disc(format_family="opticalDisc", matrix_number="CD-RUNOUT-1234")
    )
    assert disc.matrix_number == "CD-RUNOUT-1234"


@pytest.mark.parametrize("old_family", ["cd", "sacd", "cassette", "minidisc"])
def test_disc_rejects_superseded_format_families(old_family: str):
    with pytest.raises(ValidationError):
        CatalogMusicDiscResponse.model_validate(_disc(format_family=old_family))


def test_validate_music_discs_preserves_stable_ids_and_canonical_order():
    disc_id = uuid4()
    track_id = uuid4()
    credit = _credit(role="Producer", name="John")
    raw = [
        _disc(
            id=str(disc_id),
            format_family="opticalDisc",
            format="CD",
            credits=[credit],
            tracks=[
                {
                    "id": str(track_id),
                    "position": "1",
                    "position_order": 0,
                    "title": "Track 1",
                    "is_header": False,
                    "indent_level": 0,
                    "composition": "A work",
                }
            ],
        )
    ]

    normalized = validate_music_discs(raw)

    assert normalized[0]["id"] == str(disc_id)
    assert normalized[0]["format_family"] == "opticalDisc"
    assert normalized[0]["credits"][0]["id"] == credit["id"]
    assert normalized[0]["tracks"][0]["id"] == str(track_id)
    assert normalized[0]["tracks"][0]["composition"] == "A work"


def test_validate_music_discs_rejects_noncanonical_disc_order():
    with pytest.raises(ValueError, match="Discs must be ordered by disc_number"):
        validate_music_discs([_disc(number=2), _disc(number=1)])


def test_validate_music_discs_rejects_duplicate_disc_track_and_credit_ids():
    duplicate_disc_id = str(uuid4())
    with pytest.raises(ValueError, match="Disc IDs must be unique"):
        validate_music_discs([_disc(id=duplicate_disc_id), _disc(number=2, id=duplicate_disc_id)])

    duplicate_track_id = str(uuid4())
    with pytest.raises(ValueError, match="Track IDs must be unique"):
        validate_music_discs(
            [
                _disc(
                    tracks=[
                        {
                            "id": duplicate_track_id,
                            "position": "1",
                            "position_order": 0,
                            "title": "One",
                            "is_header": False,
                            "indent_level": 0,
                        }
                    ]
                ),
                _disc(
                    number=2,
                    tracks=[
                        {
                            "id": duplicate_track_id,
                            "position": "1",
                            "position_order": 0,
                            "title": "Two",
                            "is_header": False,
                            "indent_level": 0,
                        }
                    ],
                ),
            ]
        )

    duplicate_credit = _credit(role="Producer", name="John")
    with pytest.raises(ValueError, match="Credit IDs must be unique"):
        validate_music_discs(
            [
                _disc(credits=[duplicate_credit]),
                _disc(number=2, credits=[duplicate_credit]),
            ]
        )


def test_music_disc_rejects_track_order_that_needs_sorting():
    with pytest.raises(ValidationError, match="Tracks must be ordered by position_order"):
        CatalogMusicDiscResponse.model_validate(
            _disc(
                tracks=[
                    {
                        "id": str(uuid4()),
                        "position": "2",
                        "position_order": 1,
                        "title": "Second",
                        "is_header": False,
                        "indent_level": 0,
                    },
                    {
                        "id": str(uuid4()),
                        "position": "1",
                        "position_order": 0,
                        "title": "First",
                        "is_header": False,
                        "indent_level": 0,
                    },
                ]
            )
        )


def test_track_composition_is_track_metadata():
    track = CatalogMusicTrackResponse.model_validate(
        {
            "id": uuid4(),
            "position": "1",
            "position_order": 0,
            "title": "Song",
            "composition": "Symphony No. 5",
            "is_header": False,
            "indent_level": 0,
        }
    )
    assert track.composition == "Symphony No. 5"


def test_music_response_has_one_partial_date_wire_representation():
    response = CatalogMusicItemResponse.model_validate(
        _music_item(discs=[_disc(recording_date={"year": 2025, "month": 5})])
    )

    dumped = response.model_dump(mode="json", exclude_none=True)
    assert dumped["discs"][0]["recording_date"] == {"year": 2025, "month": 5}
    assert "recording_date" not in dumped
    assert "recording_date_parts" not in dumped


def test_music_catalog_writes_require_explicit_collections():
    with pytest.raises(ValueError, match="must include"):
        validate_catalog_item_payload(ItemKind.music, {"title": "Album"})


def test_music_catalog_writes_reject_unknown_root_and_nested_fields():
    with pytest.raises(ValueError, match="unrecognized fields"):
        validate_catalog_item_payload(ItemKind.music, {"title": "Album", "format": "CD"})

    payload = _proposal(discs=[_disc(legacy_format="CD")])
    with pytest.raises(ValueError, match="unrecognized fields"):
        validate_catalog_item_payload(ItemKind.music, payload)


def test_music_v2_rejects_all_old_album_level_recording_and_role_fields():
    old_fields = {
        "recording_date": {"year": 2025},
        "studios": ["Abbey Road"],
        "is_live": True,
        "spars_code": "DDD",
        "composers": [],
        "conductors": [],
        "choruses": [],
        "compositions": [],
        "orchestras": [],
        "songwriters": [],
        "producers": [],
        "engineers": [],
        "musicians": [],
    }
    for field, value in old_fields.items():
        with pytest.raises(ValueError, match="unsupported music fields"):
            validate_catalog_item_payload(ItemKind.music, _proposal(**{field: value}))

    with pytest.raises(ValidationError):
        CatalogMusicItemResponse.model_validate(_music_item(composers=[]))


def test_music_credits_allow_no_contributor_reference_and_require_instrument_list():
    credit = _credit(role="Orchestra", name="London Symphony Orchestra")
    payload = validate_catalog_item_payload(ItemKind.music, _proposal(credits=[credit]))
    assert payload["credits"][0]["id"] == credit["id"]
    assert "contributor_id" not in payload["credits"][0]

    with pytest.raises(ValueError, match="instruments"):
        validate_catalog_item_payload(
            ItemKind.music,
            _proposal(credits=[{**credit, "instruments": "violin"}]),
        )


def test_music_credit_ids_are_unique_across_album_and_disc_scopes():
    credit = _credit(role="Producer", name="John")
    with pytest.raises(ValueError, match="duplicate credit id"):
        validate_catalog_item_payload(
            ItemKind.music,
            _proposal(credits=[credit], discs=[_disc(credits=[credit])]),
        )


def test_mixed_disc_edition_preserves_recording_and_credit_scope():
    payload = _proposal(
        title="Deluxe Edition",
        discs=[
            _disc(
                number=1,
                format_family="opticalDisc",
                format="CD",
                recording_date={"year": 2025},
                sound_types=["Stereo"],
                recording_locations=["Abbey Road"],
                is_live=False,
                spars_code="DDD",
                credits=[_credit(role="Producer", name="John")],
            ),
            _disc(
                number=2,
                format_family="opticalDisc",
                format="CD",
                recording_date={"year": 2026, "month": 2, "day": 18},
                sound_types=["Stereo"],
                recording_locations=["Wembley"],
                is_live=True,
                spars_code="ADD",
                credits=[
                    _credit(role="Conductor", name="Jane", sequence=1),
                    _credit(role="Orchestra", name="LSO", sequence=2),
                ],
            ),
            _disc(
                number=3,
                format_family="vinyl",
                format='12" Vinyl',
                recording_date={"year": 2024},
                color="Red",
                rpm="45",
            ),
        ],
    )

    validated = validate_catalog_item_payload(ItemKind.music, payload)

    assert [disc["format_family"] for disc in validated["discs"]] == [
        "opticalDisc",
        "opticalDisc",
        "vinyl",
    ]
    assert validated["discs"][0]["credits"][0]["role"] == "Producer"
    assert validated["discs"][1]["credits"][1]["name"] == "LSO"
    assert "recording_date" not in validated
