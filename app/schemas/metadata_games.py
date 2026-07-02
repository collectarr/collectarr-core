from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ItemKind


class GameReleaseV1Response(BaseModel):
    id: UUID
    work_id: UUID
    release_title: str | None = None
    platform: str | None = None
    release_date: date | None = None
    region_code: str | None = None
    format: str | None = None
    publisher: str | None = None
    catalog_number: str | None = None
    barcode: str | None = None
    release_status: str | None = None
    language: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None

    model_config = {"from_attributes": True}


class GameWorkV1Response(BaseModel):
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
    company_roles: list[str] = Field(default_factory=list)
    age_ratings: list[str] = Field(default_factory=list)
    trailer_urls: list[dict[str, Any]] = Field(default_factory=list)
    external_links: list[dict[str, Any]] = Field(default_factory=list)
    kind: ItemKind = ItemKind.game
    releases: list[GameReleaseV1Response] = Field(default_factory=list)

    model_config = {"from_attributes": True}
