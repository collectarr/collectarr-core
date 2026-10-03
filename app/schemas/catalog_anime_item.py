"""Wire schemas for flattened Anime Catalog Items."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CatalogAnimeItemIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool = False

    model_config = ConfigDict(from_attributes=True, extra="allow")


class CatalogAnimeItemMediaResponse(BaseModel):
    id: UUID
    position: int = Field(ge=0)
    media_number: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(extra="allow")


class CatalogAnimeItemEpisodeResponse(BaseModel):
    id: UUID
    position: int = Field(ge=0)
    episode_number: int | None = Field(default=None, ge=0)
    title: str | None = None
    episode_title: str | None = None

    model_config = ConfigDict(extra="allow")


class CatalogAnimeItemResponse(BaseModel):
    id: UUID
    kind: Literal["anime"] = "anime"
    title: str
    sort_key: str | None = None
    revision: int

    age_rating: str | None = None
    audience_rating: str | None = None
    audio_tracks: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    character_details: list[dict[str, Any]] | None = None
    characters: list[dict[str, Any] | str] | None = None
    color: str | None = None
    contributors: list[dict[str, Any] | str] | None = None
    country: str | None = None
    cover_image_url: str | None = None
    creators: list[dict[str, Any] | str] | None = None
    description: str | None = None
    edition_title: str | None = None
    episodes: list[CatalogAnimeItemEpisodeResponse]
    external_links: list[dict[str, Any]] | None = None
    genres: list[str] | None = None
    identifiers: list[CatalogAnimeItemIdentifierResponse | str] | None = None
    item_number: str | None = None
    language: str | None = None
    layers: str | None = None
    localized_title: str | None = None
    media: list[CatalogAnimeItemMediaResponse]
    nr_discs: int | None = None
    original_title: str | None = None
    physical_format: str | None = None
    plot_description: str | None = None
    plot_summary: str | None = None
    publisher: str | None = None
    release_date: dict[str, int] | str | None = None
    release_date_parts: dict[str, int] | str | None = None
    release_status: str | None = None
    runtime_minutes: int | None = None
    screen_ratio: str | None = None
    search_aliases: list[str] | None = None
    seasons: list[dict[str, Any]] | None = None
    series_title: str | None = None
    series_tags: list[str] | None = None
    subtitle: str | None = None
    subtitles: str | None = None
    synopsis: str | None = None
    thumbnail_image_url: str | None = None
    title_extension: str | None = None
    trailer_urls: list[dict[str, Any]] | None = None
    variant_name: str | None = None

    model_config = ConfigDict(extra="forbid")
