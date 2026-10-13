"""Wire schemas for flattened Video Game Catalog Items."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.catalog_item_base import CatalogItemBaseResponse


class CatalogGameItemIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogGameItemResponse(CatalogItemBaseResponse):
    kind: Literal["game"] = "game"
    sort_key: str | None = None

    age_rating: str | None = None
    audience_rating: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    company_roles: list[str] | None = None
    contributors: list[dict[str, Any] | str] | None = None
    country: str | None = None
    cover_image_url: str | None = None
    creators: list[dict[str, Any] | str] | None = None
    description: str | None = None
    developers: list[str] | None = None
    edition_title: str | None = None
    external_links: list[dict[str, Any]] | None = None
    genres: list[str] | None = None
    identifiers: list[CatalogGameItemIdentifierResponse | str] | None = None
    item_number: str | None = None
    language: str | None = None
    languages: list[str] | None = None
    localized_title: str | None = None
    original_language: str | None = None
    original_title: str | None = None
    physical_format: str | None = None
    physical_format_label: str | None = None
    platforms: list[str] | None = None
    plot_description: str | None = None
    plot_summary: str | None = None
    publisher: str | None = None
    release_date: dict[str, int] | str | None = None
    release_date_parts: dict[str, int] | str | None = None
    release_region: str | None = None
    release_status: str | None = None
    search_aliases: list[str] | None = None
    series_tags: list[str] | None = None
    series_title: str | None = None
    franchise: str | None = None
    subtitle: str | None = None
    synopsis: str | None = None
    thumbnail_image_url: str | None = None
    title_extension: str | None = None
    toy_subtype: str | None = None
    toy_type: str | None = None
    trailer_urls: list[dict[str, Any]] | None = None
    variant_name: str | None = None

    model_config = ConfigDict(extra="forbid")
