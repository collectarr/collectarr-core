"""Metadata fields shared by board and video games."""

from app.catalog.metadata_field_spec import (
    INPUT_LIST,
    SECTION_RELATIONS,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec(
        "platforms", VALUE_TYPE_STRING_LIST, "Platforms", typed=True,
        normalized=True, section=SECTION_RELATIONS, input=INPUT_LIST,
        kinds=frozenset({ItemKind.game, ItemKind.boardgame}),
    ),
    MetadataFieldSpec(
        "identifiers", VALUE_TYPE_STRING_LIST, "Identifiers",
        section=SECTION_RELATIONS, input=INPUT_LIST,
        kinds=frozenset({ItemKind.game, ItemKind.boardgame}),
    ),
)

__all__ = ["FIELD_SPECS"]
