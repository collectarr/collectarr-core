"""Board Game Catalog Item fields and contained identifiers."""

from app.catalog.document_shape import INTEGER, STRING, KindDocumentShape
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN
from app.catalog.metadata_field_spec import (
    INPUT_LIST,
    SECTION_RELATIONS,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec("contributors", VALUE_TYPE_STRING_LIST, "Contributors",
                      section=SECTION_RELATIONS, input=INPUT_LIST,
                      kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("mechanics", VALUE_TYPE_STRING_LIST, "Mechanics",
                      section=SECTION_RELATIONS, input=INPUT_LIST,
                      kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("categories", VALUE_TYPE_STRING_LIST, "Categories",
                      section=SECTION_RELATIONS, input=INPUT_LIST,
                      kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("families", VALUE_TYPE_STRING_LIST, "Families",
                      section=SECTION_RELATIONS, input=INPUT_LIST,
                      kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("expansions", VALUE_TYPE_STRING_LIST, "Expansions",
                      section=SECTION_RELATIONS, input=INPUT_LIST,
                      kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("rankings", VALUE_TYPE_STRING_LIST, "Rankings",
                      section=SECTION_RELATIONS, input=INPUT_LIST,
                      kinds=frozenset({ItemKind.boardgame})),
)

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "contributors", "description", "identifiers", "min_players", "max_players",
            "playing_time_minutes", "min_age", "year_published", "series_title",
        }
    ),
    root_value_types={
        "description": STRING,
        "min_players": INTEGER,
        "max_players": INTEGER,
        "playing_time_minutes": INTEGER,
        "min_age": INTEGER,
        "year_published": INTEGER,
        "series_title": STRING,
    },
    children=COMMON_ROOT_CHILDREN,
)
