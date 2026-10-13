"""Released kinds keep the internal enum while exposing only public values."""

from typing import Annotated

from pydantic import AfterValidator, WithJsonSchema

from app.models.base import ItemKind

RELEASED_CATALOG_KINDS = frozenset({ItemKind.music})


def _require_released_kind(kind: ItemKind) -> ItemKind:
    if kind not in RELEASED_CATALOG_KINDS:
        raise ValueError("This kind is not included in the Music release")
    return kind


ReleasedCatalogKind = Annotated[
    ItemKind,
    AfterValidator(_require_released_kind),
    WithJsonSchema({"type": "string", "enum": sorted(kind.value for kind in RELEASED_CATALOG_KINDS)}),
]
