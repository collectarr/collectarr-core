"""Music Catalog Item fields and contained disc/track validation."""

from collections.abc import Mapping
from typing import Any

from app.catalog.document_shape import (
    BOOLEAN,
    INTEGER,
    INTEGER_OR_STRING,
    LINK,
    PERSON,
    STRING,
    STRING_LIST,
    ChildObjectShape,
    KindDocumentShape,
)
from app.catalog.metadata_field_spec import (
    INPUT_DATE,
    INPUT_LIST,
    INPUT_MULTILINE,
    INPUT_NUMBER,
    SECTION_ITEM,
    SECTION_PUBLISHING,
    SECTION_RELATIONS,
    SECTION_TECHNICAL,
    VALUE_TYPE_INTEGER,
    VALUE_TYPE_PARTIAL_DATE,
    VALUE_TYPE_STRING,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec("artist", VALUE_TYPE_STRING, "Artist", section=SECTION_ITEM,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("sort_title", VALUE_TYPE_STRING, "Sort title", section=SECTION_ITEM,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("label", VALUE_TYPE_STRING, "Label", section=SECTION_PUBLISHING,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("format", VALUE_TYPE_STRING, "Format", section=SECTION_PUBLISHING,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("original_release_date", VALUE_TYPE_PARTIAL_DATE,
                      "Original release date", section=SECTION_ITEM, input=INPUT_DATE,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("recording_date", VALUE_TYPE_PARTIAL_DATE, "Recording date",
                      section=SECTION_ITEM, input=INPUT_DATE,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("packaging", VALUE_TYPE_STRING, "Packaging",
                      section=SECTION_PUBLISHING, kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("studios", VALUE_TYPE_STRING_LIST, "Studio", section=SECTION_ITEM,
                      input=INPUT_LIST, kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("is_live", "boolean", "Is live", section=SECTION_TECHNICAL,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("sound_types", VALUE_TYPE_STRING_LIST, "Sound",
                      section=SECTION_TECHNICAL, input=INPUT_LIST,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("vinyl_color", VALUE_TYPE_STRING, "Vinyl color",
                      section=SECTION_TECHNICAL, kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("vinyl_weight", VALUE_TYPE_STRING, "Vinyl weight",
                      section=SECTION_TECHNICAL, kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("rpm", VALUE_TYPE_INTEGER, "RPM", section=SECTION_TECHNICAL,
                      input=INPUT_NUMBER, kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("extra", VALUE_TYPE_STRING, "Extra", section=SECTION_TECHNICAL,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("spars", VALUE_TYPE_STRING, "SPARS", section=SECTION_TECHNICAL,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("box_set", VALUE_TYPE_STRING, "Box set",
                      section=SECTION_TECHNICAL, kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("tracks", "object_list", "Tracks", section=SECTION_RELATIONS,
                      input=INPUT_MULTILINE, kinds=frozenset({ItemKind.music})),
)


def _validate_discs(values: list[Mapping[str, Any]], path: str) -> None:
    numbers: set[int] = set()
    ids: set[str] = set()
    track_ids: set[str] = set()
    for index, value in enumerate(values):
        number = value.get("disc_number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise ValueError(f"{path}[{index}].disc_number must be a positive integer")
        if number in numbers:
            raise ValueError(f"{path}[{index}].disc_number must be unique")
        numbers.add(number)
        disc_id = value.get("id")
        if disc_id is not None:
            if str(disc_id) in ids:
                raise ValueError(f"{path}[{index}].id must be unique")
            ids.add(str(disc_id))
        for track_index, track in enumerate(value.get("tracks", [])):
            track_id = track.get("id")
            if track_id is not None and str(track_id) in track_ids:
                raise ValueError(
                    f"{path}[{index}].tracks[{track_index}].id must be unique within the album"
                )
            if track_id is not None:
                track_ids.add(str(track_id))


TRACK = ChildObjectShape(
    fields={
        "id": STRING,
        "position": INTEGER_OR_STRING,
        "position_order": INTEGER,
        "title": STRING,
        "artist": STRING,
        "duration_ms": INTEGER,
    },
    required=frozenset({"title"}),
    non_empty=frozenset({"title"}),
    nullable=frozenset(
        {
            "id", "position", "position_order", "artist", "duration_ms",
        }
    ),
)

DISC = ChildObjectShape(
    fields={
        "id": STRING,
        "disc_number": INTEGER,
        "title": STRING,
        "matrix_number_side_a": STRING,
        "matrix_number_side_b": STRING,
    },
    nested={"tracks": TRACK},
    required=frozenset({"disc_number"}),
    nullable=frozenset(
        {
            "id", "title", "matrix_number_side_a", "matrix_number_side_b",
        }
    ),
    validate_collection=_validate_discs,
)

_CREDIT_ROLES = (
    "artist_credits", "composers", "conductors", "songwriters", "producers",
    "engineers", "musicians",
)

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "subtitle", "sort_title", "original_release_date",
            "original_release_date_parts", "label", "format", "artist_credits",
            "composers", "conductors", "choruses", "compositions", "orchestras",
            "songwriters", "producers", "engineers", "musicians", "recording_date",
            "recording_date_parts", "studios", "sound_types", "is_live", "packaging",
            "vinyl_color", "vinyl_weight", "rpm", "extra", "spars", "box_set",
            "discs", "cover_image_url", "back_cover_image_url", "thumbnail_image_url",
            "external_links",
        }
    ),
    root_value_types={
        "subtitle": STRING, "sort_title": STRING, "label": STRING, "format": STRING,
        "original_release_date": "partial_date",
        "original_release_date_parts": "partial_date",
        "recording_date": "partial_date", "recording_date_parts": "partial_date",
        "choruses": STRING_LIST, "compositions": STRING_LIST,
        "orchestras": STRING_LIST,
        "studios": STRING_LIST, "sound_types": STRING_LIST, "is_live": BOOLEAN,
        "packaging": STRING, "vinyl_color": STRING, "vinyl_weight": STRING,
        "rpm": INTEGER, "extra": STRING, "spars": STRING, "box_set": STRING,
        "cover_image_url": STRING, "back_cover_image_url": STRING,
        "thumbnail_image_url": STRING,
    },
    children={
        **dict.fromkeys(_CREDIT_ROLES, PERSON),
        "discs": DISC,
        "external_links": ChildObjectShape(
            fields=LINK.fields, nullable=frozenset(LINK.fields.keys())
        ),
    },
    explicit_root_fields=frozenset(
        {
            "title", "artist", "release_date", "release_date_parts", "genres",
            "barcode", "catalog_number", "country", "cover_image_url",
            "back_cover_image_url", "thumbnail_image_url", "external_links",
            "subtitle", "sort_title", "original_release_date",
            "original_release_date_parts", "label", "format", "artist_credits",
            "composers", "conductors", "choruses", "compositions", "orchestras",
            "songwriters", "producers", "engineers", "musicians", "recording_date",
            "recording_date_parts", "studios", "sound_types", "is_live", "packaging",
            "vinyl_color", "vinyl_weight", "rpm", "extra", "spars", "box_set", "discs",
        }
    ),
)
