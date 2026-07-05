from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind


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


class VariantResponse(BaseModel):
    id: UUID
    name: str
    variant_type: str | None
    sku: str | None
    barcode: str | None
    isbn: str | None
    region: str | None
    platform: str | None
    cover_price_cents: int | None
    currency: str | None
    cover_image_url: str | None
    thumbnail_image_url: str | None
    description: str | None
    physical_format: str | None = None
    physical_format_label: str | None = None
    is_primary: bool

    model_config = {"from_attributes": True}


class BundleReleaseContentSummaryResponse(BaseModel):
    total_items: int
    primary_count: int
    bonus_count: int


class BundleReleaseSummaryResponse(BaseModel):
    id: UUID
    kind: ItemKind
    title: str
    bundle_type: str | None = None
    format: str | None = None
    variant_type: str | None = None
    packaging_type: str | None = None
    region: str | None = None
    language: str | None = None
    publisher: str | None = None
    sku: str | None = None
    barcode: str | None = None
    release_date: date | None = None
    cover_image_url: str | None = None
    thumbnail_image_url: str | None = None
    primary_entity_type: str | None = None
    primary_entity_id: UUID | None = None
    primary_entity_title: str | None = None
    series_id: UUID | None = None
    series_title: str | None = None
    volume_id: UUID | None = None
    volume_name: str | None = None
    content_summary: BundleReleaseContentSummaryResponse


class BundleReleaseMemberResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    role: str
    sequence_number: int | None = None
    disc_number: int | None = None
    disc_label: str | None = None
    quantity: int
    is_primary: bool
    kind: ItemKind
    title: str
    item_number: str | None = None
    series_id: UUID | None = None
    series_title: str | None = None
    volume_name: str | None = None
    volume_number: float | None = None


class BundleReleaseDetailResponse(BundleReleaseSummaryResponse):
    franchise_id: UUID | None = None
    provider_links: list["ExternalProviderIdResponse"] = Field(default_factory=list)
    members: list[BundleReleaseMemberResponse] = Field(default_factory=list)


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


class EditionResponse(BaseModel):
    id: UUID
    title: str
    format: str | None
    publisher: str | None
    isbn: str | None
    upc: str | None
    language: str | None
    region: str | None
    imprint: str | None = None
    subtitle: str | None = None
    series_group: str | None = None
    age_rating: str | None = None
    catalog_number: str | None = None
    release_status: str | None = None
    release_date: date | None
    physical_format: str | None = None
    physical_format_label: str | None = None
    variants: list[VariantResponse] = []

    model_config = {"from_attributes": True}


class ExternalProviderIdResponse(BaseModel):
    provider: ExternalProvider
    entity_type: str
    provider_item_id: str
    site_url: str | None = None
    api_url: str | None = None

    model_config = {"from_attributes": True}


class CreateEditionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    format: str | None = None
    publisher: str | None = None
    isbn: str | None = None
    upc: str | None = None
    language: str | None = None
    region: str | None = None
    release_date: date | None = None


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
    publisher: str | None = None
    release_date: date | None = None
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
