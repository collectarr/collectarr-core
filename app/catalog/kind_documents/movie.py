"""Movie Catalog Item fields and contained media validation."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from app.catalog.document_shape import INTEGER, STRING, ChildObjectShape, KindDocumentShape
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN

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


def _validate_media(values: list[Mapping[str, Any]], path: str) -> None:
    seen: set[int] = set()
    for index, value in enumerate(values):
        number = value.get("media_number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise ValueError(f"{path}[{index}].media_number must be a positive integer")
        if number in seen:
            raise ValueError(f"{path}[{index}].media_number must be unique")
        seen.add(number)


MEDIA = replace(MOVIE_MEDIA, validate_collection=_validate_media)
MOVIE_PERSON = ChildObjectShape(
    fields={**COMMON_ROOT_CHILDREN["contributors"].fields, "character": STRING},
    nested=COMMON_ROOT_CHILDREN["contributors"].nested,
    required=COMMON_ROOT_CHILDREN["contributors"].required,
    non_empty=COMMON_ROOT_CHILDREN["contributors"].non_empty,
    nullable=COMMON_ROOT_CHILDREN["contributors"].nullable | frozenset({"character"}),
    allow_string_value=COMMON_ROOT_CHILDREN["contributors"].allow_string_value,
)

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "description",
            "creators",
            "contributors",
            "characters",
            "character_details",
            "media",
        }
    ),
    root_value_types={"description": STRING},
    children={
        **COMMON_ROOT_CHILDREN,
        "creators": MOVIE_PERSON,
        "contributors": MOVIE_PERSON,
        "media": MEDIA,
    },
)
