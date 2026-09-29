"""Wire schemas for flattened Manga Catalog Items."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CatalogMangaItemIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogMangaItemResponse(BaseModel):
    id: UUID
    kind: Literal["manga"] = "manga"
    title: str
    sort_key: str | None = None
    revision: int

    age_rating: str | None = None
    audience_rating: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    chapters: list[dict[str, Any]] | None = None
    character_details: list[dict[str, Any]] | None = None
    characters: list[dict[str, Any] | str] | None = None
    contributors: list[dict[str, Any] | str] | None = None
    country: str | None = None
    cover_image_url: str | None = None
    creators: list[dict[str, Any] | str] | None = None
    crossover: str | None = None
    description: str | None = None
    edition_title: str | None = None
    external_links: list[dict[str, Any]] | None = None
    genres: list[str] | None = None
    imprint: str | None = None
    isbn: str | None = None
    isbn10: str | None = None
    isbn13: str | None = None
    item_number: str | None = None
    language: str | None = None
    localized_title: str | None = None
    original_title: str | None = None
    page_count: int | None = None
    physical_format: str | None = None
    plot_description: str | None = None
    plot_summary: str | None = None
    publisher: str | None = None
    release_date: dict[str, int] | str | None = None
    release_date_parts: dict[str, int] | str | None = None
    release_status: str | None = None
    search_aliases: list[str] | None = None
    series_group: str | None = None
    series_tags: list[str] | None = None
    series_title: str | None = None
    subtitle: str | None = None
    synopsis: str | None = None
    thumbnail_image_url: str | None = None
    title_extension: str | None = None
    variant_name: str | None = None
    volume_name: str | None = None
    volume_number: str | None = None
    identifiers: list[CatalogMangaItemIdentifierResponse | str] | None = None

    model_config = ConfigDict(extra="forbid")
