"""Root metadata field specifications owned by the Movie kind."""

from app.catalog.metadata_field_spec import (
    SECTION_ITEM,
    SECTION_PUBLISHING,
    VALUE_TYPE_STRING,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

MOVIE_KINDS = frozenset({ItemKind.movie})

FIELD_SPECS = (
    MetadataFieldSpec(
        "display_title",
        VALUE_TYPE_STRING,
        "Display title",
        section=SECTION_ITEM,
        kinds=MOVIE_KINDS,
    ),
    MetadataFieldSpec(
        "original_language",
        VALUE_TYPE_STRING,
        "Original language",
        section=SECTION_PUBLISHING,
        kinds=MOVIE_KINDS,
    ),
    MetadataFieldSpec(
        "studio",
        VALUE_TYPE_STRING,
        "Studio",
        section=SECTION_PUBLISHING,
        kinds=MOVIE_KINDS,
    ),
    MetadataFieldSpec(
        "production_companies",
        VALUE_TYPE_STRING_LIST,
        "Production companies",
        section=SECTION_PUBLISHING,
        kinds=MOVIE_KINDS,
    ),
)

__all__ = ["FIELD_SPECS"]
