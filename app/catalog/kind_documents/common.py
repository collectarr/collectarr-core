"""Shared contained-value shapes explicitly composed by kind schemas."""

from app.catalog.document_shape import (
    CHARACTER,
    IDENTIFIER,
    INTEGER,
    LINK,
    PARTIAL_DATE,
    PERSON,
    STORY_ARC,
    STRING,
    ChildObjectShape,
)

CHAPTER = ChildObjectShape(
    fields={
        "id": STRING,
        "chapter_number": INTEGER,
        "title": STRING,
        "release_date": PARTIAL_DATE,
        "page_count": INTEGER,
        "position": INTEGER,
    },
    nullable=frozenset({"id", "chapter_number", "title", "release_date", "page_count", "position"}),
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
    "CHAPTER",
    "COMMON_ROOT_CHILDREN",
]
