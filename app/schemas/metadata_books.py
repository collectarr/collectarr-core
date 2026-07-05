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
    role_id: str | None = None
    biography: str | None = None
    sort_name: str | None = None


class BookOriginalDetailsResponse(BaseModel):
    original_language: str | None = None
    original_publication_date: date | None = None
    original_publisher: str | None = None
    dewey: str | None = None
    lccn: str | None = None
    loc_control_number: str | None = None


class BookPhysicalDetailsResponse(BaseModel):
    dimensions: str | None = None
    dust_jacket: bool | None = None
    printing: str | None = None
    first_edition: bool | None = None
    number_line: str | None = None
    local_cover_image_path: str | None = None
    local_back_image_path: str | None = None
    local_thumbnail_image_path: str | None = None


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
    physical_details: BookPhysicalDetailsResponse | None = None
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
    original_details: BookOriginalDetailsResponse | None = None
    kind: ItemKind = ItemKind.book
    contributors: list[BookContributorResponse] = Field(default_factory=list)
    series: list[BookSeriesResponse] = Field(default_factory=list)
    editions: list[BookEditionV1Response] = Field(default_factory=list)
