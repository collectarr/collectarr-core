"""Music Catalog Item fields and contained disc/track validation."""

from collections.abc import Mapping
from typing import Any

from app.catalog.document_shape import (
    BOOLEAN,
    INTEGER,
    INTEGER_OR_STRING,
    LINK,
    PARTIAL_DATE_OBJECT,
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
    SECTION_ITEM,
    SECTION_PUBLISHING,
    SECTION_RELATIONS,
    SECTION_TECHNICAL,
    VALUE_TYPE_PARTIAL_DATE,
    VALUE_TYPE_STRING,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec(
        "artist",
        VALUE_TYPE_STRING,
        "Artist",
        section=SECTION_ITEM,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "sort_title",
        VALUE_TYPE_STRING,
        "Sort title",
        section=SECTION_ITEM,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "label",
        VALUE_TYPE_STRING,
        "Label",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "original_release_date",
        VALUE_TYPE_PARTIAL_DATE,
        "Original release date",
        section=SECTION_ITEM,
        input=INPUT_DATE,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "recording_date",
        VALUE_TYPE_PARTIAL_DATE,
        "Recording date",
        section=SECTION_ITEM,
        input=INPUT_DATE,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "packaging",
        VALUE_TYPE_STRING,
        "Packaging",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "studios",
        VALUE_TYPE_STRING_LIST,
        "Studio",
        section=SECTION_ITEM,
        input=INPUT_LIST,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "is_live",
        "boolean",
        "Is live",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "extra",
        VALUE_TYPE_STRING_LIST,
        "Extra",
        section=SECTION_TECHNICAL,
        input=INPUT_LIST,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "spars_code",
        VALUE_TYPE_STRING,
        "SPARS code",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "box_set",
        VALUE_TYPE_STRING,
        "Box set",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "tracks",
        "object_list",
        "Tracks",
        section=SECTION_RELATIONS,
        input=INPUT_MULTILINE,
        kinds=frozenset({ItemKind.music}),
    ),
)


def _validate_discs(values: list[Mapping[str, Any]], path: str) -> None:
    from app.schemas.catalog_music_item import validate_music_discs

    # Proposals and persisted documents share Music's component/hierarchy rules.
    try:
        validate_music_discs([dict(value) for value in values])
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


TRACK = ChildObjectShape(
    fields={
        "id": STRING,
        "position": INTEGER_OR_STRING,
        "position_order": INTEGER,
        "title": STRING,
        "artist": STRING,
        "duration_ms": INTEGER,
        "is_header": BOOLEAN,
        "parent_header_id": STRING,
        "indent_level": INTEGER,
    },
    required=frozenset({"title"}),
    non_empty=frozenset({"title"}),
    nullable=frozenset(
        {
            "id",
            "position",
            "position_order",
            "artist",
            "duration_ms",
            "parent_header_id",
        }
    ),
)

DISC = ChildObjectShape(
    fields={
        "id": STRING,
        "disc_number": INTEGER,
        "title": STRING,
        "format_family": STRING,
        "format": STRING,
        "sound_types": STRING_LIST,
        "color": STRING,
        "vinyl_weight_grams": INTEGER,
        "rpm": STRING,
        "matrix_number": STRING,
        "matrix_number_side_a": STRING,
        "matrix_number_side_b": STRING,
    },
    nested={"tracks": TRACK},
    required=frozenset({"disc_number"}),
    nullable=frozenset(
        {
            "id",
            "title",
            "format_family",
            "format",
            "color",
            "vinyl_weight_grams",
            "rpm",
            "matrix_number",
            "matrix_number_side_a",
            "matrix_number_side_b",
        }
    ),
    validate_collection=_validate_discs,
)

_CREDIT_ROLES = (
    "artist_credits",
    "composers",
    "conductors",
    "songwriters",
    "producers",
    "engineers",
    "musicians",
)

_MUSIC_CREDIT = ChildObjectShape(
    fields={
        **PERSON.fields,
        "artist_id": STRING,
        "join_phrase": STRING,
        "instrument": STRING,
    },
    nullable=PERSON.nullable | frozenset({"artist_id"}),
    allow_string_value=True,
)

DOCUMENT = KindDocumentShape(
    root_fields={
        "subtitle": STRING,
        "sort_title": STRING,
        "label": STRING,
        "choruses": STRING_LIST,
        "compositions": STRING_LIST,
        "orchestras": STRING_LIST,
        "studios": STRING_LIST,
        "is_live": BOOLEAN,
        "packaging": STRING,
        "extra": STRING_LIST,
        "spars_code": STRING,
        "box_set": STRING,
        "cover_image_url": STRING,
        "back_cover_image_url": STRING,
        "thumbnail_image_url": STRING,
    },
    root_field_overrides={
        "release_date": PARTIAL_DATE_OBJECT,
        "original_release_date": PARTIAL_DATE_OBJECT,
        "recording_date": PARTIAL_DATE_OBJECT,
    },
    rejected_root_fields=frozenset(
        {
            "release_date_parts",
            "original_release_date_parts",
            "recording_date_parts",
        }
    ),
    children={
        **dict.fromkeys(_CREDIT_ROLES, _MUSIC_CREDIT),
        "discs": DISC,
        "external_links": ChildObjectShape(
            fields=LINK.fields, nullable=frozenset(LINK.fields.keys())
        ),
    },
    allowed_root_fields=frozenset(
        {
            "title",
            "artist",
            "release_date",
            "genres",
            "barcode",
            "catalog_number",
            "country",
            "cover_image_url",
            "back_cover_image_url",
            "thumbnail_image_url",
            "external_links",
            "subtitle",
            "sort_title",
            "original_release_date",
            "label",
            "artist_credits",
            "composers",
            "conductors",
            "choruses",
            "compositions",
            "orchestras",
            "songwriters",
            "producers",
            "engineers",
            "musicians",
            "recording_date",
            "studios",
            "is_live",
            "packaging",
            "extra",
            "spars_code",
            "box_set",
            "discs",
        }
    ),
    required_root_fields=frozenset({"title"}),
)
