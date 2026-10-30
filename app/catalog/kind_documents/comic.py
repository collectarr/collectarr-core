"""Comic Catalog Item fields and contained relationships."""

from dataclasses import replace

from app.catalog.document_shape import (
    BOOLEAN,
    CHARACTER,
    INTEGER,
    PARTIAL_DATE,
    PERSON,
    STRING,
    ChildObjectShape,
    KindDocumentShape,
)
from app.catalog.kind_documents.common import common_root_children
from app.catalog.metadata_field_spec import (
    INPUT_DATE,
    INPUT_LIST,
    INPUT_NUMBER,
    SECTION_ARTWORK,
    SECTION_ITEM,
    SECTION_PUBLISHING,
    SECTION_TECHNICAL,
    VALUE_TYPE_BOOLEAN,
    VALUE_TYPE_INTEGER,
    VALUE_TYPE_OBJECT_LIST,
    VALUE_TYPE_PARTIAL_DATE,
    VALUE_TYPE_STRING,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

_COMIC = frozenset({ItemKind.comic})

FIELD_SPECS = (
    MetadataFieldSpec("issue_number", VALUE_TYPE_STRING, "Issue No.", section=SECTION_ITEM, kinds=_COMIC),
    MetadataFieldSpec("variant", VALUE_TYPE_STRING, "Variant", section=SECTION_ITEM, kinds=_COMIC),
    MetadataFieldSpec(
        "variant_description", VALUE_TYPE_STRING, "Variant Description",
        section=SECTION_ITEM, kinds=_COMIC,
    ),
    MetadataFieldSpec(
        "volume_start_year", VALUE_TYPE_INTEGER, "Volume start year",
        section=SECTION_ITEM, input=INPUT_NUMBER, kinds=_COMIC,
    ),
    MetadataFieldSpec(
        "cover_date", VALUE_TYPE_PARTIAL_DATE, "Cover Date",
        section=SECTION_PUBLISHING, input=INPUT_DATE, kinds=_COMIC,
    ),
    MetadataFieldSpec(
        "release_date_parts", VALUE_TYPE_PARTIAL_DATE, "Release Date",
        section=SECTION_PUBLISHING, input=INPUT_DATE, kinds=_COMIC,
    ),
    MetadataFieldSpec(
        "cover_price_cents", VALUE_TYPE_INTEGER, "Cover Price",
        section=SECTION_PUBLISHING, input=INPUT_NUMBER, kinds=_COMIC,
    ),
    MetadataFieldSpec("currency", VALUE_TYPE_STRING, "Currency", section=SECTION_PUBLISHING, kinds=_COMIC),
    MetadataFieldSpec("key_comic", VALUE_TYPE_BOOLEAN, "Key", section=SECTION_ARTWORK, kinds=_COMIC),
    MetadataFieldSpec("key_reason", VALUE_TYPE_STRING, "Key Reason", section=SECTION_ARTWORK, kinds=_COMIC),
    MetadataFieldSpec(
        "story_arcs", VALUE_TYPE_OBJECT_LIST, "Story Arc",
        section=SECTION_TECHNICAL, input=INPUT_LIST, kinds=_COMIC, correction_only=True,
    ),
    MetadataFieldSpec(
        "creators", VALUE_TYPE_OBJECT_LIST, "Creators",
        section=SECTION_TECHNICAL, input=INPUT_LIST, kinds=_COMIC, correction_only=True,
    ),
    MetadataFieldSpec(
        "characters", VALUE_TYPE_OBJECT_LIST, "Characters",
        section=SECTION_TECHNICAL, input=INPUT_LIST, kinds=_COMIC, correction_only=True,
    ),
    MetadataFieldSpec(
        "publication_age", VALUE_TYPE_STRING, "Age",
        section=SECTION_PUBLISHING, kinds=frozenset({ItemKind.comic}),
    ),
    MetadataFieldSpec(
        "imprint",
        VALUE_TYPE_STRING,
        "Imprint",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.comic}),
    ),
    MetadataFieldSpec(
        "series_group",
        VALUE_TYPE_STRING,
        "Series group",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.comic}),
    ),
    MetadataFieldSpec(
        "page_count",
        VALUE_TYPE_INTEGER,
        "Page count",
        section=SECTION_PUBLISHING,
        input=INPUT_NUMBER,
        kinds=frozenset({ItemKind.comic}),
    ),
    MetadataFieldSpec(
        "crossover",
        VALUE_TYPE_STRING,
        "Crossover",
        section=SECTION_ARTWORK,
        kinds=frozenset({ItemKind.comic}),
    ),
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

COMIC_PERSON = ChildObjectShape(
    fields={**PERSON.fields, "join_phrase": STRING},
    nested=PERSON.nested,
    required=PERSON.required,
    non_empty=PERSON.non_empty,
    nullable=PERSON.nullable | frozenset({"join_phrase"}),
    allow_string_value=PERSON.allow_string_value,
)

DOCUMENT = KindDocumentShape(
    root_fields={
        "description": STRING,
        "series_title": STRING,
        "publication_age": STRING,
        "age_rating": STRING,
        "variant": STRING,
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
        **{
            name: replace(shape, label={
                "identifiers": "Identifiers", "external_links": "Links",
                "story_arcs": "Story Arcs",
            }[name])
            for name, shape in common_root_children(
                "identifiers", "external_links", "story_arcs"
            ).items()
        },
        "creators": replace(COMIC_PERSON, label="Creators"),
        "characters": replace(COMIC_CHARACTER, label="Characters"),
        "key_events": replace(KEY_EVENT, label="Key Events"),
    },
    required_root_fields=frozenset({"title"}),
)
