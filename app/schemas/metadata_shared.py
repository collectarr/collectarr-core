from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.catalog.release_scope import ReleasedCatalogKind
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


class CatalogSearchItemEnvelope(BaseModel):
    """A search hit with catalog fields owned by its kind."""

    id: UUID
    kind: ReleasedCatalogKind
    kind_data: dict[str, Any]

    model_config = ConfigDict(extra="forbid")


class CatalogSearchPage(BaseModel):
    """A stable page of flattened Catalog Item search results."""

    items: list[CatalogSearchItemEnvelope]
    next_offset: int | None
    has_more: bool

    model_config = ConfigDict(extra="forbid")


class CatalogItemPage[T](BaseModel):
    """A stable offset page for kind-specific Catalog Item responses."""

    items: list[T]
    next_offset: int | None
    has_more: bool

    model_config = ConfigDict(extra="forbid")


def catalog_item_page[T](rows: list[T], *, limit: int, offset: int) -> CatalogItemPage[T]:
    """Build a page from a query that fetched one look-ahead row."""

    has_more = len(rows) > limit
    items = rows[:limit]
    return CatalogItemPage(
        items=items,
        next_offset=offset + len(items) if has_more else None,
        has_more=has_more,
    )
