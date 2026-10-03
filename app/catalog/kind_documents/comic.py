"""Comic Catalog Item fields and contained relationships."""

from app.catalog.document_shape import BOOLEAN, INTEGER, STRING, KindDocumentShape
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "creators", "contributors", "description", "characters", "character_details",
            "story_arcs", "identifiers", "series_title", "volume_name", "issue_number",
            "cover_price_cents", "currency", "key_comic", "key_reason",
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
    },
    children=COMMON_ROOT_CHILDREN,
)
