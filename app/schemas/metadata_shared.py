from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.base import ItemKind


def public_item_kind(kind: Any) -> ItemKind | None:
    if kind is None:
        return None
    if isinstance(kind, str):
        normalized = kind.strip().lower()
        try:
            return ItemKind(normalized)
        except ValueError:
            return None
    return kind if isinstance(kind, ItemKind) else None


class MetadataCredit(BaseModel):
    name: str
    role: str | None = None
    api_detail_url: str | None = None
    site_detail_url: str | None = None
    image_url: str | None = None

    model_config = {"extra": "allow"}


class ContributorResponse(BaseModel):
    person_id: UUID
    name: str
    role: str
    sequence: int | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


class CatalogSearchItemEnvelope(BaseModel):
    """A search hit with catalog fields owned by its kind."""

    id: UUID
    kind: ItemKind
    kind_data: dict[str, Any]

    model_config = ConfigDict(extra="forbid")
