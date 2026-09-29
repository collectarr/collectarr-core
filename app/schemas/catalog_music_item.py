"""Wire schemas for flattened Music catalog items."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CatalogMusicTrackResponse(BaseModel):
    id: UUID
    position: str
    position_order: int
    title: str
    artist: str | None = None
    duration_ms: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CatalogMusicDiscResponse(BaseModel):
    id: UUID
    disc_number: int
    title: str | None = None
    matrix_number_side_a: str | None = None
    matrix_number_side_b: str | None = None
    tracks: list[CatalogMusicTrackResponse]

    model_config = ConfigDict(from_attributes=True)


class CatalogMusicItemResponse(BaseModel):
    id: UUID
    kind: str = "music"
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    artist: str | None = None
    artist_credits: list[dict[str, Any]]
    original_release_date: date | None = None
    original_release_date_parts: dict[str, int] | str | None = None
    recording_date: date | None = None
    recording_date_parts: dict[str, int] | str | None = None
    release_date: date | None = None
    release_date_parts: dict[str, int] | str | None = None
    label: str | None = None
    format: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    genres: list[str]
    packaging: str | None = None
    studios: list[str]
    country: str | None = None
    is_live: bool | None = None
    sound_types: list[str]
    vinyl_color: str | None = None
    vinyl_weight: str | None = None
    rpm: int | None = None
    extra: str | None = None
    spars: str | None = None
    box_set: str | None = None
    composers: list[dict[str, Any]]
    conductors: list[dict[str, Any]]
    choruses: list[str]
    compositions: list[str]
    orchestras: list[str]
    songwriters: list[dict[str, Any]]
    producers: list[dict[str, Any]]
    engineers: list[dict[str, Any]]
    musicians: list[dict[str, Any]]
    external_links: list[dict[str, Any]]
    cover_image_url: str | None = None
    back_cover_image_url: str | None = None
    thumbnail_image_url: str | None = None
    revision: int
    discs: list[CatalogMusicDiscResponse]

    model_config = ConfigDict(from_attributes=True)
