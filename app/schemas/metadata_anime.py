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

# Anime DTOs
class AnimeContributorResponse(ContributorResponse):
    id: UUID


class AnimeIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    is_primary: bool


class AnimeCharacterResponse(BaseModel):
    id: UUID
    character_id: UUID
    character_name: str
    role: str


class AnimeEpisodeV1Response(BaseModel):
    id: UUID
    series_id: UUID
    episode_number: float | None = None
    episode_title: str | None = None
    air_date: date | None = None
    description: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    runtime_minutes: int | None = None

    model_config = {"from_attributes": True}


class AnimeSeriesV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    description: str | None = None
    original_language: str | None = None
    original_air_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    anime_type: str | None = None
    episode_count: int | None = None
    kind: ItemKind = ItemKind.anime
    episodes: list[AnimeEpisodeV1Response] = Field(default_factory=list)
    contributions: list[AnimeContributorResponse] = Field(default_factory=list)
    identifiers: list[AnimeIdentifierResponse] = Field(default_factory=list)
    character_appearances: list[AnimeCharacterResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
