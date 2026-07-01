from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.catalog.grouping_models import GroupingModel
from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.metadata_normalized import typed_kind_metadata_for_item
from app.models.base import ExternalProvider, ItemKind
from app.schemas.metadata_shared import (
    BundleReleaseContentSummaryResponse,
    BundleReleaseDetailResponse,
    BundleReleaseMemberResponse,
    BundleReleaseSummaryResponse,
    ContributorResponse,
    ExternalProviderIdResponse,
    MetadataCredit,
    public_item_kind,
)

class ComicContributorResponse(ContributorResponse):
    scope: str


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
    kind: ItemKind = ItemKind.comic
    contributors: list[ComicContributorResponse] = Field(default_factory=list)
    issues: list[ComicIssueV1Response] = Field(default_factory=list)
