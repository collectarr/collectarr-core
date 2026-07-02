from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ItemKind


class BoardGameEditionV1Response(BaseModel):
    id: UUID
    work_id: UUID
    edition_title: str | None = None
    format: str | None = None
    release_date: date | None = None
    publisher: str | None = None
    catalog_number: str | None = None
    barcode: str | None = None
    release_status: str | None = None
    language: str | None = None
    country: str | None = None
    age_rating: str | None = None
    audience_rating: str | None = None
    min_players: int | None = None
    max_players: int | None = None
    playing_time_minutes: int | None = None
    min_age: int | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}


class BoardGameWorkV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    release_date: date | None = None
    original_language: str | None = None
    publisher: str | None = None
    age_rating: str | None = None
    audience_rating: str | None = None
    search_aliases: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    identifiers: list[str] = Field(default_factory=list)
    contributors: list[str] = Field(default_factory=list)
    mechanics: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    families: list[str] = Field(default_factory=list)
    expansions: list[str] = Field(default_factory=list)
    rankings: list[str] = Field(default_factory=list)
    trailer_urls: list[dict[str, Any]] = Field(default_factory=list)
    external_links: list[dict[str, Any]] = Field(default_factory=list)
    kind: ItemKind = ItemKind.boardgame
    editions: list[BoardGameEditionV1Response] = Field(default_factory=list)

    model_config = {"from_attributes": True}
