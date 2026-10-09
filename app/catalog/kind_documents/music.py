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
    VALUE_TYPE_OBJECT_LIST,
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
        "packaging",
        VALUE_TYPE_STRING,
        "Packaging",
        section=SECTION_PUBLISHING,
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
        "box_set",
        VALUE_TYPE_STRING,
        "Box set",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.music}),
    ),
    MetadataFieldSpec(
        "artist_credits",
        VALUE_TYPE_OBJECT_LIST,
        "Artist credits",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.music}),
        correction_only=True,
    ),
    MetadataFieldSpec(
        "credits",
        VALUE_TYPE_OBJECT_LIST,
        "Credits",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.music}),
        correction_only=True,
    ),
    MetadataFieldSpec(
        "discs",
        VALUE_TYPE_OBJECT_LIST,
        "Discs",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.music}),
        correction_only=True,
    ),
)


def _validate_discs(values: list[Mapping[str, Any]], path: str) -> None:
    from app.schemas.catalog_music_item import validate_music_discs

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


def _validate_music_credits(values: list[Mapping[str, Any]], path: str) -> None:
    from app.schemas.catalog_music_item import CatalogMusicCreditResponse

    seen_ids: set[str] = set()
    seen_sequences: set[int] = set()
    for index, value in enumerate(values):
        try:
            credit = CatalogMusicCreditResponse.model_validate(value)
        except ValueError as error:
            raise ValueError(f"{path}[{index}]: {error}") from error
        if str(credit.id) in seen_ids or credit.sequence in seen_sequences:
            raise ValueError(f"{path}[{index}] duplicates a credit identity or sequence")
        seen_ids.add(str(credit.id))
        seen_sequences.add(credit.sequence)


def _validate_music_external_links(values: list[Mapping[str, Any]], path: str) -> None:
    from app.schemas.catalog_music_item import CatalogMusicExternalLinkResponse

    for index, value in enumerate(values):
        try:
            CatalogMusicExternalLinkResponse.model_validate(value)
        except ValueError as error:
            raise ValueError(f"{path}[{index}]: {error}") from error


def _validate_music_document(value: Mapping[str, Any], path: str) -> None:
    for key, field_value in value.items():
        field_path = f"{path}.{key}"
        if isinstance(field_value, str):
            if not field_value or field_value != field_value.strip():
                raise ValueError(f"{field_path} must be non-empty trimmed text")
        elif key in {"genres", "extra"} and isinstance(field_value, list):
            for index, entry in enumerate(field_value):
                if not entry or entry != entry.strip():
                    raise ValueError(f"{field_path}[{index}] must be non-empty trimmed text")

    album_credit_ids = {
        str(credit.get("id")) for credit in value.get("credits", []) if isinstance(credit, Mapping)
    }
    disc_credit_ids: set[str] = set()
    for disc in value.get("discs", []):
        if not isinstance(disc, Mapping):
            continue
        for credit in disc.get("credits", []):
            if isinstance(credit, Mapping) and "id" in credit:
                credit_id = str(credit["id"])
                if credit_id in album_credit_ids or credit_id in disc_credit_ids:
                    raise ValueError(f"{path}.discs contains a duplicate credit id: {credit_id}")
                disc_credit_ids.add(credit_id)


TRACK = ChildObjectShape(
    fields={
        "id": STRING,
        "position": STRING,
        "position_order": INTEGER,
        "title": STRING,
        "artist": STRING,
        "composition": STRING,
        "duration_ms": INTEGER,
        "is_header": BOOLEAN,
        "parent_header_id": STRING,
        "indent_level": INTEGER,
    },
    required=frozenset({"id", "position", "position_order", "title", "is_header", "indent_level"}),
    non_empty=frozenset({"title"}),
    nullable=frozenset({"artist", "composition", "duration_ms", "parent_header_id"}),
)

CREDIT = ChildObjectShape(
    fields={
        "id": STRING,
        "contributor_id": STRING,
        "name": STRING,
        "sort_name": STRING,
        "role": STRING,
        "role_id": STRING,
        "instruments": STRING_LIST,
        "sequence": INTEGER,
    },
    required=frozenset({"id", "name", "role", "instruments", "sequence"}),
    non_empty=frozenset({"id", "name", "role"}),
    nullable=frozenset({"contributor_id", "sort_name", "role_id"}),
    validate_collection=_validate_music_credits,
)

DISC = ChildObjectShape(
    fields={
        "id": STRING,
        "disc_number": INTEGER,
        "title": STRING,
        "format_family": STRING,
        "format": STRING,
        "sound_types": STRING_LIST,
        "recording_date": PARTIAL_DATE_OBJECT,
        "recording_locations": STRING_LIST,
        "is_live": BOOLEAN,
        "spars_code": STRING,
        "color": STRING,
        "vinyl_weight_grams": INTEGER,
        "rpm": STRING,
        "matrix_number": STRING,
        "matrix_number_side_a": STRING,
        "matrix_number_side_b": STRING,
    },
    nested={"credits": CREDIT, "tracks": TRACK},
    required=frozenset(
        {"id", "disc_number", "sound_types", "recording_locations", "credits", "tracks"}
    ),
    nullable=frozenset(
        {
            "title",
            "format_family",
            "format",
            "recording_date",
            "is_live",
            "spars_code",
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
    nullable=frozenset({"artist_id", "sort_name", "join_phrase"}),
    validate_collection=_validate_music_artist_credits,
)

DOCUMENT = KindDocumentShape(
    root_fields={
        "subtitle": STRING,
        "sort_title": STRING,
        "label": STRING,
        "packaging": STRING,
        "extra": STRING_LIST,
        "box_set": STRING,
        "cover_image_url": STRING,
        "back_cover_image_url": STRING,
        "thumbnail_image_url": STRING,
    },
    root_field_overrides={
        "release_date": PARTIAL_DATE_OBJECT,
        "original_release_date": PARTIAL_DATE_OBJECT,
    },
    rejected_root_fields=frozenset(
        {
            "release_date_parts",
            "original_release_date_parts",
            "recording_date",
            "studios",
            "is_live",
            "spars_code",
            "composers",
            "conductors",
            "choruses",
            "compositions",
            "orchestras",
            "songwriters",
            "producers",
            "engineers",
            "musicians",
        }
    ),
    children={
        "artist_credits": _MUSIC_ARTIST_CREDIT,
        "credits": CREDIT,
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
            "credits",
            "packaging",
            "extra",
            "box_set",
            "discs",
        }
    ),
    required_root_fields=frozenset(
        {"title", "artist_credits", "credits", "genres", "extra", "external_links", "discs"}
    ),
    validate_document=_validate_music_document,
    reject_unknown_fields=True,
)
