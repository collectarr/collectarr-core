"""Shared contained-value shapes explicitly composed by kind schemas."""

from app.catalog.document_shape import (
    CHARACTER,
    IDENTIFIER,
    LINK,
    PERSON,
    STORY_ARC,
    ChildObjectShape,
)

COMMON_ROOT_CHILDREN = {
    "creators": PERSON,
    "contributors": PERSON,
    "identifiers": IDENTIFIER,
    "external_links": LINK,
    "trailer_urls": LINK,
    "characters": CHARACTER,
    "character_details": ChildObjectShape(
        fields=CHARACTER.fields,
        nullable=CHARACTER.nullable,
    ),
    "story_arcs": STORY_ARC,
}

__all__ = [
    "COMMON_ROOT_CHILDREN",
]
