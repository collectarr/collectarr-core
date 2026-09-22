from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ItemKind
from app.models.partial_date import PartialDateValue
from app.schemas.metadata_shared import (
    ContributorResponse,
)


# Manga DTOs
class MangaContributorResponse(ContributorResponse):
    id: UUID


class MangaIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    is_primary: bool


class MangaCharacterResponse(BaseModel):
    id: UUID
    character_id: UUID
    character_name: str
    role: str


class MangaChapterV1Response(BaseModel):
    id: UUID
    work_id: UUID
    chapter_number: float | None = None
    chapter_title: str | None = None
    publication_date: date | None = None
    publication_date_parts: PartialDateValue | None = None
    page_count: int | None = None
    description: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None

    model_config = {"from_attributes": True}


class MangaEditionV1Response(BaseModel):
    id: UUID
    work_id: UUID
    display_title: str | None = None
    edition_statement: str | None = None
    format: str | None = None
    binding: str | None = None
    publication_date: date | None = None
    publication_date_parts: PartialDateValue | None = None
    publisher: str | None = None
    imprint: str | None = None
    language: str | None = None
    country: str | None = None
    isbn10: str | None = None
    isbn13: str | None = None
    barcode: str | None = None
    page_count: int | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}


class MangaSeriesResponse(BaseModel):
    id: UUID
    title: str
    slug: str | None = None
    sequence: float | None = None
    display_number: str | None = None
    start_date: date | None = None
    start_date_parts: PartialDateValue | None = None
    end_date: date | None = None
    end_date_parts: PartialDateValue | None = None


class MangaWorkV1Response(BaseModel):
    id: UUID
    title: str
    volume_number: float | None = None
    sort_title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    original_language: str | None = None
    original_publication_date: date | None = None
    original_publication_date_parts: PartialDateValue | None = None
    first_publication_date: date | None = None
    first_publication_date_parts: PartialDateValue | None = None
    status: str | None = None
    kind: ItemKind = ItemKind.manga
    series: list[MangaSeriesResponse] = Field(default_factory=list)
    chapters: list[MangaChapterV1Response] = Field(default_factory=list)
    contributions: list[MangaContributorResponse] = Field(default_factory=list)
    identifiers: list[MangaIdentifierResponse] = Field(default_factory=list)
    character_appearances: list[MangaCharacterResponse] = Field(default_factory=list)
    editions: list[MangaEditionV1Response] = Field(default_factory=list)

    model_config = {"from_attributes": True}
