"""Manga Catalog Item fields and contained chapters/identifiers."""

from app.catalog.document_shape import STRING, KindDocumentShape
from app.catalog.kind_documents.common import CHAPTER, COMMON_ROOT_CHILDREN
from app.catalog.metadata_field_spec import (
    SECTION_ARTWORK,
    VALUE_TYPE_STRING,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec("crossover", VALUE_TYPE_STRING, "Crossover",
                      section=SECTION_ARTWORK,
                      kinds=frozenset({ItemKind.manga})),
)

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "creators", "contributors", "description", "characters", "chapters",
            "character_details", "identifiers", "series_title", "volume_name",
            "volume_number", "isbn", "isbn10", "isbn13",
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
    children={**COMMON_ROOT_CHILDREN, "chapters": CHAPTER},
)
