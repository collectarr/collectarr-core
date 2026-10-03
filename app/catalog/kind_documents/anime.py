"""Anime Catalog Item fields and contained episode/media schemas."""

from app.catalog.document_shape import (
    INTEGER,
    PARTIAL_DATE,
    STRING,
    ChildObjectShape,
    KindDocumentShape,
)
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN

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
            "id",
            "media_number",
            "media_type",
            "title",
            "episode_count",
            "runtime_minutes",
            "region_code",
            "encoding",
            "aspect_ratio",
            "audio_tracks",
            "subtitles",
            "resolution",
            "hdr_format",
        }
    ),
)

ANIME_EPISODE = ChildObjectShape(
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
            "id",
            "season_number",
            "episode_number",
            "episode_title",
            "title",
            "description",
            "overview",
            "air_date",
            "original_air_date",
            "runtime_minutes",
            "page_count",
        }
    ),
)

ANIME_SEASON = ChildObjectShape(
    fields={
        "id": STRING,
        "season_number": INTEGER,
        "title": STRING,
        "description": STRING,
        "air_date": PARTIAL_DATE,
        "release_date": PARTIAL_DATE,
        "episode_count": INTEGER,
    },
    nested={"episodes": ANIME_EPISODE},
    required=frozenset({"season_number"}),
    nullable=frozenset({"id", "title", "description", "air_date", "release_date", "episode_count"}),
)

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "description",
            "creators",
            "contributors",
            "characters",
            "character_details",
            "identifiers",
            "seasons",
            "episodes",
            "media",
            "series_title",
        }
    ),
    root_value_types={"description": STRING, "series_title": STRING},
    children={
        **COMMON_ROOT_CHILDREN,
        "media": ANIME_MEDIA,
        "episodes": ANIME_EPISODE,
        "seasons": ANIME_SEASON,
    },
)
