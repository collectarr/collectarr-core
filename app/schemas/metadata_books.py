from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind
from app.schemas.metadata_shared import (
    ContributorResponse,
)


class BookContributorResponse(ContributorResponse):
    scope: str


class BookIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool
    source_provider: ExternalProvider | None = None


class BookEditionV1Response(BaseModel):
    id: UUID
    work_id: UUID
    display_title: str | None = None
    edition_statement: str | None = None
    format: str | None = None
    binding: str | None = None
    publication_date: date | None = None
    publisher: str | None = None
    imprint: str | None = None
    language: str | None = None
    region: str | None = None
    page_count: int | None = None
    audio_length_minutes: int | None = None
    age_rating: str | None = None
    release_status: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    description: str | None = None
    contributors: list[BookContributorResponse] = Field(default_factory=list)
    identifiers: list[BookIdentifierResponse] = Field(default_factory=list)


class BookSeriesResponse(BaseModel):
    id: UUID
    title: str
    slug: str | None = None
    sequence: float | None = None
    display_number: str | None = None


class BookWorkV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    original_language: str | None = None
    original_publication_date: date | None = None
    first_publication_date: date | None = None
    kind: ItemKind = ItemKind.book
    contributors: list[BookContributorResponse] = Field(default_factory=list)
    series: list[BookSeriesResponse] = Field(default_factory=list)
    editions: list[BookEditionV1Response] = Field(default_factory=list)
