"""Shared contained-value shapes explicitly composed by kind schemas."""

from app.catalog.document_shape import (
    BOOLEAN,
    INTEGER,
    PARTIAL_DATE,
    STRING,
    STRING_LIST,
    ChildObjectShape,
    CHARACTER,
    IDENTIFIER,
    LINK,
    PERSON,
    STORY_ARC,
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
            "id", "media_type", "title", "aspect_ratio", "screen_ratio", "color",
            "num_discs", "nr_layers", "layers", "audio_tracks", "subtitles",
        }
    ),
)

ANIME_MEDIA = ChildObjectShape(
    fields={
        "id": STRING,
        "position": INTEGER,
        "media_number": INTEGER,
        "media_type": STRING,
        "title": STRING,
        "episode_count": INTEGER,
        "runtime_minutes": INTEGER,
        "region_code": STRING,
        "encoding": STRING,
        "aspect_ratio": STRING,
        "audio_tracks": STRING,
        "subtitles": STRING,
        "resolution": STRING,
        "hdr_format": STRING,
    },
    required=frozenset({"position"}),
    nullable=frozenset(
        {
            "id", "media_number", "media_type", "title", "episode_count",
            "runtime_minutes", "region_code", "encoding", "aspect_ratio",
            "audio_tracks", "subtitles", "resolution", "hdr_format",
        }
    ),
)

TV_MEDIA = ChildObjectShape(
    fields={
        **ANIME_MEDIA.fields,
        "color": STRING,
        "layers": STRING,
        "frame_rate": STRING,
        "bit_depth": INTEGER,
    },
    required=ANIME_MEDIA.required,
    nullable=ANIME_MEDIA.nullable | frozenset({"color", "layers", "frame_rate", "bit_depth"}),
)

EPISODE = ChildObjectShape(
    fields={
        "id": STRING,
        "season_number": INTEGER,
        "episode_number": INTEGER,
        "episode_title": STRING,
        "title": STRING,
        "description": STRING,
        "overview": STRING,
        "air_date": PARTIAL_DATE,
        "original_air_date": PARTIAL_DATE,
        "runtime_minutes": INTEGER,
        "page_count": INTEGER,
        "position": INTEGER,
    },
    required=frozenset({"position"}),
    nullable=frozenset(
        {
            "id", "season_number", "episode_number", "episode_title", "title",
            "description", "overview", "air_date", "original_air_date",
            "runtime_minutes", "page_count",
        }
    ),
)

SEASON = ChildObjectShape(
    fields={
        "id": STRING,
        "season_number": INTEGER,
        "title": STRING,
        "description": STRING,
        "air_date": PARTIAL_DATE,
        "release_date": PARTIAL_DATE,
        "episode_count": INTEGER,
    },
    nested={"episodes": EPISODE},
    required=frozenset({"season_number"}),
    nullable=frozenset(
        {"id", "title", "description", "air_date", "release_date", "episode_count"}
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
    nullable=frozenset(
        {"id", "chapter_number", "title", "release_date", "page_count", "position"}
    ),
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
    "ANIME_MEDIA", "CHAPTER", "COMMON_ROOT_CHILDREN", "EPISODE",
    "MOVIE_MEDIA", "PRINTING", "SEASON", "SERIES_MEMBERSHIP", "TV_MEDIA",
]
