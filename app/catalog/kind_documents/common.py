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

PRINTING = ChildObjectShape(
    fields={
        "id": STRING,
        "printing_number": INTEGER,
        "title": STRING,
        "release_date": PARTIAL_DATE,
        "publisher": STRING,
        "language": STRING,
        "isbn": STRING,
    },
    nullable=frozenset(
        {"id", "printing_number", "title", "release_date", "publisher", "language", "isbn"}
    ),
)

SERIES_MEMBERSHIP = ChildObjectShape(
    fields={
        "id": STRING,
        "series_id": STRING,
        "sequence": "number",
        "display_number": STRING,
    },
    required=frozenset({"series_id"}),
    non_empty=frozenset({"series_id"}),
    nullable=frozenset({"id", "sequence", "display_number"}),
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
    "PRINTING",
    "SERIES_MEMBERSHIP",
]
