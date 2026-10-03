"""Wire schemas for flattened Comic Catalog Items."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CatalogComicItemIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool = False

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogComicCreatorResponse(BaseModel):
    id: str | None = None
    person_id: str | None = None
    artist_id: str | None = None
    name: str | None = None
    role: str | None = None
    role_id: str | None = None
    sequence: int | None = None
    credited_name: str | None = None
    join_phrase: str | None = None
    image_url: str | None = None
    sort_name: str | None = None
    instrument: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogComicCharacterResponse(BaseModel):
    id: str | None = None
    character_id: str | None = None
    real_name: str | None = None
    name: str | None = None
    aliases: list[str] | None = None
    role: str | None = None
    description: str | None = None
    image_url: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogComicStoryArcResponse(BaseModel):
    id: str | None = None
    story_arc_id: str | None = None
    name: str | None = None
    description: str | None = None
    publisher: str | None = None
    start_date: dict[str, int] | str | None = None
    end_date: dict[str, int] | str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogComicLinkResponse(BaseModel):
    id: str | None = None
    label: str | None = None
    title: str | None = None
    url: str | None = None
    site: str | None = None
    name: str | None = None
    kind: str | None = None
    description: str | None = None
    position: int | None = None
    link_type: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogComicKeyEventResponse(BaseModel):
    type: str
    character_or_subject: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogComicItemResponse(BaseModel):
    id: UUID
    kind: Literal["comic"] = "comic"
    title: str
    sort_key: str | None = None
    revision: int

    age_rating: str | None = None
    audience_rating: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    cover_date: dict[str, int] | str | None = None
    characters: list[CatalogComicCharacterResponse | str] | None = None
    character_details: list[CatalogComicCharacterResponse] | None = None
    contributors: list[CatalogComicCreatorResponse | str] | None = None
    country: str | None = None
    cover_image_url: str | None = None
    cover_price_cents: int | None = None
    creators: list[CatalogComicCreatorResponse | str] | None = None
    crossover: str | None = None
    currency: str | None = None
    description: str | None = None
    edition_title: str | None = None
    external_links: list[CatalogComicLinkResponse] | None = None
    genres: list[str] | None = None
    imprint: str | None = None
    issue_number: str | None = None
    item_number: str | None = None
    key_comic: bool | None = None
    key_reason: str | None = None
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
    story_arcs: list[CatalogComicStoryArcResponse | str] | None = None
    subtitle: str | None = None
    synopsis: str | None = None
    thumbnail_image_url: str | None = None
    title_extension: str | None = None
    variant_name: str | None = None
    volume_name: str | None = None
    volume_number: str | None = None
    identifiers: list[CatalogComicItemIdentifierResponse | str] | None = None
    key_events: list[CatalogComicKeyEventResponse] | None = None
    variant_description: str | None = None
    volume_start_year: int | None = None

    model_config = ConfigDict(extra="forbid")
