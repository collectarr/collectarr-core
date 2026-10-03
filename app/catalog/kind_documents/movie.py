"""Movie Catalog Item fields and contained media validation."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from app.catalog.document_shape import KindDocumentShape
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN, MOVIE_MEDIA


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

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "description", "creators", "contributors", "characters", "character_details",
            "media",
        }
    ),
    root_value_types={"description": "string"},
    children={**COMMON_ROOT_CHILDREN, "media": MEDIA},
)
