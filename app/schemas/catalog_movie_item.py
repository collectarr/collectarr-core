"""Wire schemas for flattened Movie Catalog Items."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CatalogMovieItemMediaResponse(BaseModel):
    id: UUID
    media_number: int
    media_type: str | None = None
    title: str | None = None
    aspect_ratio: str | None = None
    screen_ratio: str | None = None
    color: str | None = None
    num_discs: int | None = None
    nr_layers: int | None = None
    layers: str | None = None
    audio_tracks: str | None = None
    subtitles: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class CatalogMovieItemResponse(BaseModel):
    id: UUID
    kind: Literal["movie"] = "movie"
    title: str
    sort_key: str | None = None
    revision: int

    original_title: str | None = None
    localized_title: str | None = None
    title_extension: str | None = None
    subtitle: str | None = None
    edition_title: str | None = None
    variant_name: str | None = None
    item_number: str | None = None
    release_date: dict[str, int] | str | None = None
    release_date_parts: dict[str, int] | str | None = None
    release_status: str | None = None
    publisher: str | None = None
    country: str | None = None
    language: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    physical_format: str | None = None
    runtime_minutes: int | None = None
    nr_discs: int | None = None
    age_rating: str | None = None
    audience_rating: str | None = None
    description: str | None = None
    synopsis: str | None = None
    plot_summary: str | None = None
    plot_description: str | None = None
    genres: list[str] | None = None
    series_tags: list[str] | None = None
    search_aliases: list[str] | None = None
    creators: list[dict[str, Any] | str] | None = None
    contributors: list[dict[str, Any] | str] | None = None
    characters: list[dict[str, Any] | str] | None = None
    character_details: list[dict[str, Any]] | None = None
    external_links: list[dict[str, Any]] | None = None
    trailer_urls: list[dict[str, Any]] | None = None
    cover_image_url: str | None = None
    thumbnail_image_url: str | None = None
    color: str | None = None
    screen_ratio: str | None = None
    audio_tracks: str | None = None
    subtitles: str | None = None
    layers: str | None = None
    discs: list[dict[str, Any]] | None = None
    media: list[CatalogMovieItemMediaResponse]

    model_config = ConfigDict(extra="forbid")
