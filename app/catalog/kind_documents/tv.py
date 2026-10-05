"""TV Catalog Item fields and contained season/media/episode schemas."""

from collections.abc import Mapping
from typing import Any

from app.catalog.document_shape import (
    INTEGER,
    PARTIAL_DATE,
    PERSON,
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
        kinds=frozenset({ItemKind.tv}),
    ),
    MetadataFieldSpec(
        "runtime_minutes",
        VALUE_TYPE_INTEGER,
        "Runtime minutes",
        section=SECTION_PUBLISHING,
        input=INPUT_NUMBER,
        kinds=frozenset({ItemKind.tv}),
    ),
    MetadataFieldSpec(
        "nr_discs",
        VALUE_TYPE_INTEGER,
        "Number of discs",
        section=SECTION_TECHNICAL,
        input=INPUT_NUMBER,
        kinds=frozenset({ItemKind.tv}),
    ),
    MetadataFieldSpec(
        "screen_ratio",
        VALUE_TYPE_STRING,
        "Screen ratio",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.tv}),
    ),
    MetadataFieldSpec(
        "audio_tracks",
        VALUE_TYPE_STRING,
        "Audio tracks",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.tv}),
    ),
    MetadataFieldSpec(
        "subtitles",
        VALUE_TYPE_STRING,
        "Subtitles",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.tv}),
    ),
    MetadataFieldSpec(
        "layers",
        VALUE_TYPE_STRING,
        "Layers",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.tv}),
    ),
)

TV_PERSON = ChildObjectShape(
    fields={**PERSON.fields, "character": STRING},
    nullable=PERSON.nullable | frozenset({"character"}),
    allow_string_value=True,
)

TV_MEDIA = ChildObjectShape(
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
        "color": STRING,
        "layers": STRING,
        "frame_rate": STRING,
        "bit_depth": INTEGER,
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
            "color",
            "layers",
            "frame_rate",
            "bit_depth",
        }
    ),
)

TV_EPISODE = ChildObjectShape(
    fields={
        "id": STRING,
        "media_id": STRING,
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
            "media_id",
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

TV_SEASON = ChildObjectShape(
    fields={
        "id": STRING,
        "season_number": INTEGER,
        "title": STRING,
        "description": STRING,
        "air_date": PARTIAL_DATE,
        "release_date": PARTIAL_DATE,
        "episode_count": INTEGER,
    },
    nested={"episodes": TV_EPISODE},
    required=frozenset({"season_number"}),
    nullable=frozenset({"id", "title", "description", "air_date", "release_date", "episode_count"}),
)


def _validate_media_references(document: Mapping[str, Any], path: str) -> None:
    media_ids: set[str] = set()
    for media in document.get("media") or []:
        if isinstance(media, Mapping):
            media_id = media.get("id")
            if isinstance(media_id, str) and media_id.strip():
                media_ids.add(media_id)

    episodes = list(document.get("episodes") or [])
    for season in document.get("seasons") or []:
        if isinstance(season, Mapping):
            episodes.extend(season.get("episodes") or [])

    for index, episode in enumerate(episodes):
        if not isinstance(episode, Mapping):
            continue
        media_id = episode.get("media_id")
        if media_id is not None and media_id not in media_ids:
            raise ValueError(
                f"{path}.episodes[{index}].media_id must reference a media id "
                "contained in this Catalog Item."
            )


DOCUMENT = KindDocumentShape(
    root_fields={"description": STRING, "series_title": STRING},
    children={
        **common_root_children(
            "identifiers",
            "external_links",
            "trailer_urls",
        ),
        "creators": TV_PERSON,
        "contributors": TV_PERSON,
        "media": TV_MEDIA,
        "episodes": TV_EPISODE,
        "seasons": TV_SEASON,
    },
    validate_document=_validate_media_references,
)
