"""Wire schemas for flattened Board Game Catalog Items."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CatalogBoardGameItemIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogBoardGameItemResponse(BaseModel):
    id: UUID
    kind: Literal["boardgame"] = "boardgame"
    title: str
    sort_key: str | None = None
    revision: int

    age_rating: str | None = None
    audience_rating: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    categories: list[str] | None = None
    contributors: list[dict[str, Any] | str] | None = None
    country: str | None = None
    cover_image_url: str | None = None
    description: str | None = None
    edition_title: str | None = None
    expansions: list[str] | None = None
    external_links: list[dict[str, Any]] | None = None
    families: list[str] | None = None
    genres: list[str] | None = None
    identifiers: list[CatalogBoardGameItemIdentifierResponse | str] | None = None
    item_number: str | None = None
    language: str | None = None
    localized_title: str | None = None
    max_players: int | None = None
    mechanics: list[str] | None = None
    min_age: int | None = None
    min_players: int | None = None
    original_title: str | None = None
    physical_format: str | None = None
    platforms: list[str] | None = None
    playing_time_minutes: int | None = None
    plot_description: str | None = None
    plot_summary: str | None = None
    publisher: str | None = None
    rankings: list[str] | None = None
    release_date: dict[str, int] | str | None = None
    release_date_parts: dict[str, int] | str | None = None
    release_status: str | None = None
    search_aliases: list[str] | None = None
    series_tags: list[str] | None = None
    subtitle: str | None = None
    synopsis: str | None = None
    thumbnail_image_url: str | None = None
    title_extension: str | None = None
    variant_name: str | None = None
    year_published: int | None = None

    model_config = ConfigDict(extra="forbid")
