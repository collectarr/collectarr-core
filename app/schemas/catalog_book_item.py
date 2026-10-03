"""Wire schemas for flattened Book Catalog Items."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CatalogBookItemPrintingResponse(BaseModel):
    id: UUID
    printing_number: int | None = None
    title: str | None = None
    release_date: Any | None = None
    publisher: str | None = None
    language: str | None = None
    isbn: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class CatalogBookItemCreditResponse(BaseModel):
    id: UUID
    person_id: UUID | None = None
    name: str
    role: str | None = None
    role_id: str | None = None
    sequence: int | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class CatalogBookItemIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str | None = None
    is_primary: bool = False

    model_config = ConfigDict(from_attributes=True, extra="allow")


class CatalogBookItemSeriesMembershipResponse(BaseModel):
    id: UUID
    series_id: UUID
    sequence: float | None = None
    display_number: str | None = None

    model_config = ConfigDict(extra="allow")


class CatalogBookItemCharacterResponse(BaseModel):
    id: str | None = None
    character_id: str | None = None
    name: str | None = None
    aliases: list[str] | None = None
    role: str | None = None
    description: str | None = None
    image_url: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogBookItemResponse(BaseModel):
    id: UUID
    kind: Literal["book"] = "book"
    title: str
    sort_key: str | None = None
    revision: int

    age_rating: str | None = None
    audience_rating: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    contributors: list[CatalogBookItemCreditResponse | str] | None = None
    characters: list[CatalogBookItemCharacterResponse | str] | None = None
    country: str | None = None
    cover_image_url: str | None = None
    back_cover_image_url: str | None = None
    creators: list[CatalogBookItemCreditResponse | str] | None = None
    description: str | None = None
    distributor: str | None = None
    dimensions: str | None = None
    edition_title: str | None = None
    edition_statement: str | None = None
    external_links: list[dict[str, Any]] | None = None
    genres: list[str] | None = None
    identifiers: list[CatalogBookItemIdentifierResponse | str] | None = None
    imprint: str | None = None
    isbn: str | None = None
    isbn10: str | None = None
    isbn13: str | None = None
    item_number: str | None = None
    first_edition: bool | None = None
    first_publication_date: Any | None = None
    audio_length_minutes: int | None = None
    binding: str | None = None
    language: str | None = None
    localized_title: str | None = None
    original_title: str | None = None
    original_language: str | None = None
    original_publication_date: Any | None = None
    page_count: int | None = None
    physical_format: str | None = None
    plot_description: str | None = None
    plot_summary: str | None = None
    printings: list[CatalogBookItemPrintingResponse] | None = None
    series_memberships: list[CatalogBookItemSeriesMembershipResponse] = Field(default_factory=list)
    publisher: str | None = None
    release_date: Any | None = None
    release_date_parts: Any | None = None
    release_status: str | None = None
    search_aliases: list[str] | None = None
    series_group: str | None = None
    series_tags: list[str] | None = None
    series_title: str | None = None
    subjects: list[str] | None = None
    region: str | None = None
    subtitle: str | None = None
    synopsis: str | None = None
    thumbnail_image_url: str | None = None
    title_extension: str | None = None
    variant_name: str | None = None
    volume_name: str | None = None
    volume_number: str | None = None

    model_config = ConfigDict(extra="forbid")
