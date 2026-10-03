"""Manga Catalog Item fields and contained chapters/identifiers."""

from app.catalog.document_shape import (
    INTEGER,
    PARTIAL_DATE,
    STRING,
    ChildObjectShape,
    KindDocumentShape,
)
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN
from app.catalog.metadata_field_spec import (
    SECTION_ARTWORK,
    VALUE_TYPE_STRING,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
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
    root_fields=frozenset(
        {
            "creators",
            "contributors",
            "description",
            "characters",
            "chapters",
            "character_details",
            "identifiers",
            "series_title",
            "volume_name",
            "volume_number",
            "isbn",
            "isbn10",
            "isbn13",
        }
    ),
    root_value_types={
        "description": STRING,
        "series_title": STRING,
        "volume_name": STRING,
        "volume_number": STRING,
        "isbn": STRING,
        "isbn10": STRING,
        "isbn13": STRING,
    },
    children={**COMMON_ROOT_CHILDREN, "chapters": MANGA_CHAPTER},
)
