from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind
from app.models.partial_date import PartialDateValue
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


class ComicVariantV1Response(BaseModel):
    id: UUID
    issue_id: UUID
    variant_name: str | None = None
    variant_type: str | None = None
    cover_label: str | None = None
    printing_number: int | None = None
    publisher: str | None = None
    imprint: str | None = None
    publication_date: date | None = None
    publication_date_parts: PartialDateValue | None = None
    release_date: date | None = None
    release_date_parts: PartialDateValue | None = None
    language: str | None = None
    region: str | None = None
    physical_format: str | None = None
    catalog_number: str | None = None
    barcode: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}


class ComicIssueV1Response(BaseModel):
    id: UUID
    work_id: UUID
    issue_number: str | None = None
    display_title: str | None = None
    publication_date: date | None = None
    publication_date_parts: PartialDateValue | None = None
    release_date: date | None = None
    release_date_parts: PartialDateValue | None = None
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
    key_comic: bool = False
    key_reason: str | None = None
    description: str | None = None
    contributors: list[ComicContributorResponse] = Field(default_factory=list)
    identifiers: list[ComicIdentifierResponse] = Field(default_factory=list)
    characters: list[ComicCharacterResponse] = Field(default_factory=list)
    story_arcs: list[ComicStoryArcResponse] = Field(default_factory=list)
    variants: list[ComicVariantV1Response] = Field(default_factory=list)


class ComicWorkV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    original_language: str | None = None
    first_publication_date: date | None = None
    first_publication_date_parts: PartialDateValue | None = None
    expected_issue_count: int | None = None
    missing_issue_count: int | None = None
    missing_issue_numbers: list[int] = Field(default_factory=list)
    kind: ItemKind = ItemKind.comic
    contributors: list[ComicContributorResponse] = Field(default_factory=list)
    issues: list[ComicIssueV1Response] = Field(default_factory=list)
