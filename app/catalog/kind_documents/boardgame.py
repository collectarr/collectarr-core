"""Board Game Catalog Item fields and contained identifiers."""

from app.catalog.document_shape import INTEGER, STRING
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN
from app.catalog.document_shape import KindDocumentShape

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "contributors", "description", "identifiers", "min_players", "max_players",
            "playing_time_minutes", "min_age", "year_published",
        }
    ),
    root_value_types={
        "description": STRING,
        "min_players": INTEGER,
        "max_players": INTEGER,
        "playing_time_minutes": INTEGER,
        "min_age": INTEGER,
        "year_published": INTEGER,
    },
    children=COMMON_ROOT_CHILDREN,
)
