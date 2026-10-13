"""Manga Catalog Item fields and contained chapters/identifiers."""

from app.catalog.document_shape import (
    INTEGER,
    PARTIAL_DATE,
    STRING,
    ChildObjectShape,
    KindDocumentShape,
)
from app.catalog.kind_documents.common import common_root_children
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
        "imprint",
        VALUE_TYPE_STRING,
        "Imprint",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.manga}),
    ),
    MetadataFieldSpec(
        "series_group",
        VALUE_TYPE_STRING,
        "Series group",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.manga}),
    ),
    MetadataFieldSpec(
        "page_count",
        VALUE_TYPE_INTEGER,
        "Page count",
        section=SECTION_PUBLISHING,
        input=INPUT_NUMBER,
        kinds=frozenset({ItemKind.manga}),
    ),
    MetadataFieldSpec(
        "crossover",
        VALUE_TYPE_STRING,
        "Crossover",
        section=SECTION_ARTWORK,
        kinds=frozenset({ItemKind.manga}),
    ),
)

MANGA_CHAPTER = ChildObjectShape(
    fields={
        "id": STRING,
        "chapter_number": INTEGER,
        "title": STRING,
        "release_date": PARTIAL_DATE,
        "page_count": INTEGER,
        "position": INTEGER,
    },
    nullable=frozenset(
        {
            "id",
            "chapter_number",
            "title",
            "release_date",
            "page_count",
            "position",
        }
    ),
)

DOCUMENT = KindDocumentShape(
    root_fields={
        "description": STRING,
        "series_title": STRING,
        "volume_name": STRING,
        "volume_number": STRING,
        "isbn": STRING,
        "isbn10": STRING,
        "isbn13": STRING,
    },
    children={
        **common_root_children(
            "creators",
            "contributors",
            "identifiers",
            "external_links",
            "characters",
            "character_details",
        ),
        "chapters": MANGA_CHAPTER,
    },
    required_root_fields=frozenset({"title"}),
)
