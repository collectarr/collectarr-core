"""Video Game Catalog Item fields and contained identifiers."""

from app.catalog.document_shape import STRING, STRING_LIST, KindDocumentShape
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN
from app.catalog.metadata_field_spec import (
    INPUT_LIST,
    SECTION_RELATIONS,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec("company_roles", VALUE_TYPE_STRING_LIST, "Company roles",
                      section=SECTION_RELATIONS, input=INPUT_LIST,
                      kinds=frozenset({ItemKind.game})),
)

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "creators", "contributors", "description", "identifiers", "platforms",
            "developers", "company_roles", "series_title", "release_region",
        }
    ),
    root_value_types={
        "description": STRING,
        "developers": STRING_LIST,
        "series_title": STRING,
        "release_region": STRING,
    },
    children=COMMON_ROOT_CHILDREN,
)
