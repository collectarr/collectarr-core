"""Comic Catalog Item fields and contained relationships."""

from app.catalog.document_shape import (
    BOOLEAN,
    CHARACTER,
    INTEGER,
    PARTIAL_DATE,
    STRING,
    ChildObjectShape,
    KindDocumentShape,
)
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN
from app.catalog.metadata_field_spec import (
    INPUT_NUMBER,
    SECTION_ARTWORK,
    SECTION_PUBLISHING,
    VALUE_TYPE_INTEGER,
    VALUE_TYPE_STRING,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec(
        "imprint", VALUE_TYPE_STRING, "Imprint",
        section=SECTION_PUBLISHING, kinds=frozenset({ItemKind.comic}),
    ),
    MetadataFieldSpec(
        "series_group", VALUE_TYPE_STRING, "Series group",
        section=SECTION_PUBLISHING, kinds=frozenset({ItemKind.comic}),
    ),
    MetadataFieldSpec(
        "page_count", VALUE_TYPE_INTEGER, "Page count",
        section=SECTION_PUBLISHING, input=INPUT_NUMBER,
        kinds=frozenset({ItemKind.comic}),
    ),
    MetadataFieldSpec("crossover", VALUE_TYPE_STRING, "Crossover",
                      section=SECTION_ARTWORK,
                      kinds=frozenset({ItemKind.comic})),
)

KEY_EVENT = ChildObjectShape(
    fields={
        "type": STRING,
        "character_or_subject": STRING,
        "description": STRING,
    },
    required=frozenset({"type", "character_or_subject"}),
    non_empty=frozenset({"type", "character_or_subject"}),
    nullable=frozenset({"description"}),
)

COMIC_CHARACTER = ChildObjectShape(
    fields={**CHARACTER.fields, "real_name": STRING},
    nullable=CHARACTER.nullable | frozenset({"real_name"}),
    allow_string_value=True,
)

COMIC_CHARACTER_DETAIL = ChildObjectShape(
    fields=COMIC_CHARACTER.fields,
    nullable=COMIC_CHARACTER.nullable,
)

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "creators", "contributors", "description", "characters", "character_details",
            "story_arcs", "identifiers", "series_title", "volume_name", "issue_number",
            "cover_price_cents", "currency", "key_comic", "key_reason",
            "cover_date", "variant_description", "key_events", "volume_number",
            "volume_start_year",
        }
    ),
    root_value_types={
        "description": STRING,
        "series_title": STRING,
        "volume_name": STRING,
        "issue_number": STRING,
        "cover_price_cents": INTEGER,
        "currency": STRING,
        "key_comic": BOOLEAN,
        "key_reason": STRING,
        "cover_date": PARTIAL_DATE,
        "variant_description": STRING,
        "volume_number": STRING,
        "volume_start_year": INTEGER,
    },
    children={
        **COMMON_ROOT_CHILDREN,
        "characters": COMIC_CHARACTER,
        "character_details": COMIC_CHARACTER_DETAIL,
        "key_events": KEY_EVENT,
    },
)
