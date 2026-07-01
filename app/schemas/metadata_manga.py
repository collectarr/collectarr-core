from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ItemKind
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
    page_count: int | None = None
    description: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None

    model_config = {"from_attributes": True}


class MangaSeriesResponse(BaseModel):
    id: UUID
    title: str
    slug: str | None = None
    sequence: float | None = None
    display_number: str | None = None


class MangaWorkV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    original_language: str | None = None
    original_publication_date: date | None = None
    first_publication_date: date | None = None
    status: str | None = None
    kind: ItemKind = ItemKind.manga
    series: list[MangaSeriesResponse] = Field(default_factory=list)
    chapters: list[MangaChapterV1Response] = Field(default_factory=list)
    contributions: list[MangaContributorResponse] = Field(default_factory=list)
    identifiers: list[MangaIdentifierResponse] = Field(default_factory=list)
    character_appearances: list[MangaCharacterResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
