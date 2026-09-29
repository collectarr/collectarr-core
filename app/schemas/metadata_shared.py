from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.base import ItemKind
from app.models.partial_date import PartialDateValue


def public_item_kind(kind: Any) -> ItemKind | None:
    if kind is None:
        return None
    if isinstance(kind, str):
        normalized = kind.strip().lower()
        try:
            return ItemKind(normalized)
        except ValueError:
            return None
    return kind if isinstance(kind, ItemKind) else None


class MetadataCredit(BaseModel):
    name: str
    role: str | None = None
    api_detail_url: str | None = None
    site_detail_url: str | None = None
    image_url: str | None = None

    model_config = {"extra": "allow"}


class ContributorResponse(BaseModel):
    person_id: UUID
    name: str
    role: str
    sequence: int | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


class SearchResult(BaseModel):
    id: UUID
    kind: ItemKind
    title: str
    item_number: str | None = None
    synopsis: str | None = None
    runtime_minutes: int | None = None
    cover_image_url: str | None = None
    thumbnail_image_url: str | None = None
    edition_title: str | None = None
    physical_format: str | None = None
    physical_format_label: str | None = None
    artist: str | None = None
    publisher: str | None = None
    release_date: date | None = None
    release_date_parts: PartialDateValue | None = None
    release_year: int | None = None
    barcode: str | None = None
    variant: str | None = None
    crossover: str | None = None
    plot_summary: str | None = None
    plot_description: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    track_count: int | None = None
    tracks: list[dict[str, Any]] | None = None
    catalog_number: str | None = None
    creators: list[dict[str, Any]] | None = None
    characters: list[str] | None = None
    character_details: list[dict[str, Any]] | None = None
    story_arcs: list[str] | None = None
    platforms: list[str] | None = None
    genres: list[str] | None = None
    page_count: int | None = None
    cover_price_cents: int | None = None
    currency: str | None = None
    country: str | None = None
    release_status: str | None = None
    language: str | None = None
    age_rating: str | None = None
    imprint: str | None = None
    subtitle: str | None = None
    series_group: str | None = None
    bundle_titles: list[str] | None = None
    bundle_release_ids: list[str] | None = None
