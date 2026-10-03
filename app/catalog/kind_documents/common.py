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

MOVIE_MEDIA = ChildObjectShape(
    fields={
        "id": STRING,
        "media_number": INTEGER,
        "media_type": STRING,
        "title": STRING,
        "aspect_ratio": STRING,
        "screen_ratio": STRING,
        "color": STRING,
        "num_discs": INTEGER,
        "nr_layers": INTEGER,
        "layers": STRING,
        "audio_tracks": STRING,
        "subtitles": STRING,
    },
    required=frozenset({"media_number"}),
    nullable=frozenset(
        {
            "id",
            "media_type",
            "title",
            "aspect_ratio",
            "screen_ratio",
            "color",
            "num_discs",
            "nr_layers",
            "layers",
            "audio_tracks",
            "subtitles",
        }
    ),
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
    "MOVIE_MEDIA",
    "PRINTING",
    "SERIES_MEMBERSHIP",
]
