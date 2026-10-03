"""Anime Catalog Item fields and contained episode/media schemas."""

from app.catalog.document_shape import STRING
from app.catalog.kind_documents.common import ANIME_MEDIA, COMMON_ROOT_CHILDREN, EPISODE, SEASON
from app.catalog.document_shape import KindDocumentShape

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "description", "creators", "contributors", "characters", "character_details",
            "identifiers", "seasons", "episodes", "discs", "media", "series_title",
        }
    ),
    root_value_types={"description": STRING, "series_title": STRING},
    children={
        **COMMON_ROOT_CHILDREN,
        "media": ANIME_MEDIA,
        "episodes": EPISODE,
        "seasons": SEASON,
    },
)
