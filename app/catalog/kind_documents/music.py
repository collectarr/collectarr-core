"""Music Catalog Item fields and contained disc/track validation."""

from collections.abc import Mapping
from typing import Any

from app.catalog.document_shape import (
    BOOLEAN,
    INTEGER,
    PARTIAL_DATE_OBJECT,
    STRING,
    STRING_LIST,
    ChildObjectShape,
    KindDocumentShape,
)
from app.catalog.metadata_field_spec import (
    INPUT_DATE,
    INPUT_LIST,
    SECTION_ITEM,
    SECTION_PUBLISHING,
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
)


def _validate_discs(values: list[Mapping[str, Any]], path: str) -> None:
    from app.schemas.catalog_music_item import validate_music_discs

    # Proposals and persisted documents share Music's component/hierarchy rules.
    try:
        validate_music_discs([dict(value) for value in values])
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def _validate_music_artist_credits(values: list[Mapping[str, Any]], path: str) -> None:
    from app.schemas.catalog_music_item import CatalogMusicArtistCreditResponse

    seen_ids: set[str] = set()
    seen_sequences: set[int] = set()
    for index, value in enumerate(values):
        try:
            credit = CatalogMusicArtistCreditResponse.model_validate(value)
        except ValueError as error:
            raise ValueError(f"{path}[{index}]: {error}") from error
        if credit.id in seen_ids or credit.sequence in seen_sequences:
            raise ValueError(f"{path}[{index}] duplicates a credit identity or sequence")
        seen_ids.add(credit.id)
        seen_sequences.add(credit.sequence)


def _validate_music_role_credits(values: list[Mapping[str, Any]], path: str) -> None:
    from app.schemas.catalog_music_item import CatalogMusicRoleCreditResponse

    seen_ids: set[str] = set()
    seen_sequences: set[int] = set()
    for index, value in enumerate(values):
        try:
            credit = CatalogMusicRoleCreditResponse.model_validate(value)
        except ValueError as error:
            raise ValueError(f"{path}[{index}]: {error}") from error
        if credit.id in seen_ids or credit.sequence in seen_sequences:
            raise ValueError(f"{path}[{index}] duplicates a credit identity or sequence")
        seen_ids.add(credit.id)
        seen_sequences.add(credit.sequence)


def _validate_music_external_links(values: list[Mapping[str, Any]], path: str) -> None:
    from app.schemas.catalog_music_item import CatalogMusicExternalLinkResponse

    for index, value in enumerate(values):
        try:
            CatalogMusicExternalLinkResponse.model_validate(value)
        except ValueError as error:
            raise ValueError(f"{path}[{index}]: {error}") from error


_STRING_LIST_FIELDS = frozenset(
    {"genres", "studios", "extra", "choruses", "compositions", "orchestras"}
)


def _validate_music_document(value: Mapping[str, Any], path: str) -> None:
    for key, field_value in value.items():
        field_path = f"{path}.{key}"
        if isinstance(field_value, str):
            if not field_value or field_value != field_value.strip():
                raise ValueError(f"{field_path} must be non-empty trimmed text")
        elif key in _STRING_LIST_FIELDS and isinstance(field_value, list):
            for index, entry in enumerate(field_value):
                if not entry or entry != entry.strip():
                    raise ValueError(f"{field_path}[{index}] must be non-empty trimmed text")


TRACK = ChildObjectShape(
    fields={
        "id": STRING,
        "position": STRING,
        "position_order": INTEGER,
        "title": STRING,
        "artist": STRING,
        "duration_ms": INTEGER,
        "is_header": BOOLEAN,
        "parent_header_id": STRING,
        "indent_level": INTEGER,
    },
    required=frozenset({"id", "position", "position_order", "title", "is_header", "indent_level"}),
    non_empty=frozenset({"title"}),
    nullable=frozenset(
        {
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
    required=frozenset({"id", "disc_number", "sound_types", "tracks"}),
    nullable=frozenset(
        {
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
    "composers",
    "conductors",
    "songwriters",
    "producers",
    "engineers",
    "musicians",
)

_MUSIC_ARTIST_CREDIT = ChildObjectShape(
    fields={
        "id": STRING,
        "name": STRING,
        "sort_name": STRING,
        "artist_id": STRING,
        "sequence": INTEGER,
        "join_phrase": STRING,
    },
    required=frozenset({"id", "name", "sequence"}),
    non_empty=frozenset({"id", "name"}),
    nullable=frozenset({"artist_id"}),
    validate_collection=_validate_music_artist_credits,
)

_MUSIC_ROLE_CREDIT = ChildObjectShape(
    fields={
        "id": STRING,
        "name": STRING,
        "person_id": STRING,
        "role_id": STRING,
        "sequence": INTEGER,
        "sort_name": STRING,
        "image_url": STRING,
        "instrument": STRING,
    },
    required=frozenset({"id", "name", "person_id", "sequence"}),
    non_empty=frozenset({"id", "name", "person_id"}),
    validate_collection=_validate_music_role_credits,
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
        "artist_credits": _MUSIC_ARTIST_CREDIT,
        **dict.fromkeys(_CREDIT_ROLES, _MUSIC_ROLE_CREDIT),
        "discs": DISC,
        "external_links": ChildObjectShape(
            fields={"url": STRING, "title": STRING, "description": STRING},
            required=frozenset({"url"}),
            non_empty=frozenset({"url", "title", "description"}),
            nullable=frozenset({"title", "description"}),
            validate_collection=_validate_music_external_links,
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
    required_root_fields=frozenset(
        {
            "title",
            "artist_credits",
            "genres",
            "studios",
            "extra",
            "composers",
            "conductors",
            "choruses",
            "compositions",
            "orchestras",
            "songwriters",
            "producers",
            "engineers",
            "musicians",
            "external_links",
            "discs",
        }
    ),
    validate_document=_validate_music_document,
    reject_unknown_fields=True,
)
