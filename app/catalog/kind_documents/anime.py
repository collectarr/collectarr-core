"""Anime Catalog Item fields and contained episode/media schemas."""

from app.catalog.document_shape import (
    INTEGER,
    PARTIAL_DATE,
    STRING,
    ChildObjectShape,
    KindDocumentShape,
)
from app.catalog.kind_documents.common import common_root_children
from app.catalog.metadata_field_spec import (
    INPUT_NUMBER,
    SECTION_PUBLISHING,
    SECTION_TECHNICAL,
    VALUE_TYPE_INTEGER,
    VALUE_TYPE_STRING,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec(
        "color",
        VALUE_TYPE_STRING,
        "Color",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.anime}),
    ),
    MetadataFieldSpec(
        "runtime_minutes",
        VALUE_TYPE_INTEGER,
        "Runtime minutes",
        section=SECTION_PUBLISHING,
        input=INPUT_NUMBER,
        kinds=frozenset({ItemKind.anime}),
    ),
    MetadataFieldSpec(
        "nr_discs",
        VALUE_TYPE_INTEGER,
        "Number of discs",
        section=SECTION_TECHNICAL,
        input=INPUT_NUMBER,
        kinds=frozenset({ItemKind.anime}),
    ),
    MetadataFieldSpec(
        "screen_ratio",
        VALUE_TYPE_STRING,
        "Screen ratio",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.anime}),
    ),
    MetadataFieldSpec(
        "audio_tracks",
        VALUE_TYPE_STRING,
        "Audio tracks",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.anime}),
    ),
    MetadataFieldSpec(
        "subtitles",
        VALUE_TYPE_STRING,
        "Subtitles",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.anime}),
    ),
    MetadataFieldSpec(
        "layers",
        VALUE_TYPE_STRING,
        "Layers",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.anime}),
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
    root_fields={"description": STRING, "series_title": STRING},
    children={
        **common_root_children(
            "creators",
            "contributors",
            "identifiers",
            "external_links",
            "trailer_urls",
            "characters",
            "character_details",
        ),
        "media": ANIME_MEDIA,
        "episodes": ANIME_EPISODE,
        "seasons": ANIME_SEASON,
    },
    required_root_fields=frozenset({"title"}),
)
