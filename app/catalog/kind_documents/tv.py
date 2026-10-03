"""TV Catalog Item fields and contained season/media/episode schemas."""

from app.catalog.document_shape import STRING, KindDocumentShape
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN, EPISODE, SEASON, TV_MEDIA

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "description", "creators", "contributors", "characters", "character_details",
            "identifiers", "seasons", "episodes", "discs", "media",
        }
    ),
    root_value_types={"description": STRING},
    children={
        **COMMON_ROOT_CHILDREN,
        "media": TV_MEDIA,
        "episodes": EPISODE,
        "seasons": SEASON,
    },
)
