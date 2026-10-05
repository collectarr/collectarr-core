"""Video Game Catalog Item fields and contained identifiers."""

from app.catalog.document_shape import STRING, STRING_LIST, KindDocumentShape
from app.catalog.kind_documents.common import common_root_children
from app.catalog.metadata_field_spec import (
    INPUT_LIST,
    INPUT_TEXT,
    SECTION_ITEM,
    SECTION_REGIONAL,
    SECTION_RELATIONS,
    VALUE_TYPE_STRING,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec(
        "platforms",
        VALUE_TYPE_STRING_LIST,
        "Platforms",
        section=SECTION_RELATIONS,
        input=INPUT_LIST,
        kinds=frozenset({ItemKind.game}),
    ),
    MetadataFieldSpec(
        "identifiers",
        VALUE_TYPE_STRING_LIST,
        "Identifiers",
        section=SECTION_RELATIONS,
        input=INPUT_LIST,
        kinds=frozenset({ItemKind.game}),
    ),
    MetadataFieldSpec(
        "toy_subtype",
        VALUE_TYPE_STRING,
        "Toy subtype",
        section=SECTION_ITEM,
        input=INPUT_TEXT,
        kinds=frozenset({ItemKind.game}),
    ),
    MetadataFieldSpec(
        "toy_type",
        VALUE_TYPE_STRING,
        "Toy type",
        section=SECTION_ITEM,
        input=INPUT_TEXT,
        kinds=frozenset({ItemKind.game}),
    ),
    MetadataFieldSpec(
        "company_roles",
        VALUE_TYPE_STRING_LIST,
        "Company roles",
        section=SECTION_RELATIONS,
        input=INPUT_LIST,
        kinds=frozenset({ItemKind.game}),
    ),
    MetadataFieldSpec(
        "franchise",
        VALUE_TYPE_STRING,
        "Franchise",
        section=SECTION_RELATIONS,
        input=INPUT_TEXT,
        kinds=frozenset({ItemKind.game}),
    ),
    MetadataFieldSpec(
        "original_language",
        VALUE_TYPE_STRING,
        "Original language",
        section=SECTION_REGIONAL,
        input=INPUT_TEXT,
        kinds=frozenset({ItemKind.game}),
    ),
    MetadataFieldSpec(
        "languages",
        VALUE_TYPE_STRING_LIST,
        "Languages",
        section=SECTION_REGIONAL,
        input=INPUT_LIST,
        kinds=frozenset({ItemKind.game}),
    ),
)

DOCUMENT = KindDocumentShape(
    root_fields={
        "description": STRING,
        "developers": STRING_LIST,
        "series_title": STRING,
        "release_region": STRING,
        "physical_format_label": STRING,
        "toy_subtype": STRING,
        "toy_type": STRING,
    },
    children=common_root_children(
        "creators",
        "contributors",
        "identifiers",
        "external_links",
        "trailer_urls",
    ),
)
