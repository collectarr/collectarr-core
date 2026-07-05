from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind
from app.schemas.metadata_shared import (
    ContributorResponse,
)


class ComicContributorResponse(ContributorResponse):
    scope: str
    role_id: str | None = None


class ComicIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool
    source_provider: ExternalProvider | None = None


class ComicCharacterResponse(BaseModel):
    character_id: UUID
    name: str
    role: str
    image_url: str | None = None
    sort_name: str | None = None
    external_ids: dict[str, str] | None = None


class ComicStoryArcResponse(BaseModel):
    story_arc_id: UUID
    name: str
    ordinal: int | None = None


class ComicIssueV1Response(BaseModel):
    id: UUID
    work_id: UUID
    issue_number: str | None = None
    display_title: str | None = None
    publication_date: date | None = None
    release_date: date | None = None
    publisher: str | None = None
    imprint: str | None = None
    language: str | None = None
    region: str | None = None
    page_count: int | None = None
    cover_price_cents: int | None = None
    currency: str | None = None
    release_status: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    local_image_path: str | None = None
    value_cents: int | None = None
    value_currency: str | None = None
    grade: str | None = None
    grading_company: str | None = None
    raw_or_slabbed: str | None = None
    storage_box: str | None = None
    key_comic: bool = False
    key_reason: str | None = None
    description: str | None = None
    contributors: list[ComicContributorResponse] = Field(default_factory=list)
    identifiers: list[ComicIdentifierResponse] = Field(default_factory=list)
    characters: list[ComicCharacterResponse] = Field(default_factory=list)
    story_arcs: list[ComicStoryArcResponse] = Field(default_factory=list)


class ComicWorkV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    original_language: str | None = None
    first_publication_date: date | None = None
    expected_issue_count: int | None = None
    owned_issue_count: int | None = None
    missing_issue_count: int | None = None
    missing_issue_numbers: list[int] = Field(default_factory=list)
    kind: ItemKind = ItemKind.comic
    contributors: list[ComicContributorResponse] = Field(default_factory=list)
    issues: list[ComicIssueV1Response] = Field(default_factory=list)
