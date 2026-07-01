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

# Movie DTOs
class MovieContributorResponse(ContributorResponse):
    id: UUID
    character_name: str | None = None


class MovieIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    is_primary: bool


class MovieCharacterResponse(BaseModel):
    id: UUID
    character_id: UUID
    character_name: str
    role: str


class MovieReleaseMediaResponse(BaseModel):
    id: UUID
    release_id: UUID
    media_number: int | None = None
    media_type: str | None = None
    title: str | None = None
    aspect_ratio: str | None = None
    screen_ratio: str | None = None
    color: str | None = None
    num_discs: int | None = None
    nr_layers: int | None = None
    layers: str | None = None
    audio_tracks: str | None = None
    subtitles: str | None = None

    model_config = {"from_attributes": True}


class MovieReleaseV1Response(BaseModel):
    id: UUID
    work_id: UUID
    release_title: str | None = None
    release_date: date | None = None
    region: str | None = None
    format: str | None = None
    distributor: str | None = None
    language: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    trailer_urls: list[dict[str, Any]] = Field(default_factory=list)
    external_links: list[dict[str, Any]] = Field(default_factory=list)
    media: list[MovieReleaseMediaResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MovieWorkV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    original_language: str | None = None
    release_date: date | None = None
    runtime_minutes: int | None = None
    age_rating: str | None = None
    audience_rating: str | None = None
    trailer_urls: list[dict[str, Any]] = Field(default_factory=list)
    external_links: list[dict[str, Any]] = Field(default_factory=list)
    kind: ItemKind = ItemKind.movie
    releases: list[MovieReleaseV1Response] = Field(default_factory=list)
    contributions: list[MovieContributorResponse] = Field(default_factory=list)
    identifiers: list[MovieIdentifierResponse] = Field(default_factory=list)
    character_appearances: list[MovieCharacterResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}

# TV DTOs
class TVContributorResponse(ContributorResponse):
    id: UUID


class TVIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    is_primary: bool


class TVCharacterResponse(BaseModel):
    id: UUID
    character_id: UUID
    character_name: str
    role: str


class TVReleaseMediaResponse(BaseModel):
    id: UUID
    release_id: UUID
    media_number: int | None = None
    media_type: str | None = None
    title: str | None = None
    episode_count: int | None = None
    runtime_minutes: int | None = None
    region_code: str | None = None
    encoding: str | None = None
    aspect_ratio: str | None = None
    color: str | None = None
    audio_tracks: str | None = None
    subtitles: str | None = None
    layers: str | None = None
    frame_rate: str | None = None
    bit_depth: str | None = None
    resolution: str | None = None
    hdr_format: str | None = None

    model_config = {"from_attributes": True}


class TVEpisodeV1Response(BaseModel):
    id: UUID
    season_id: UUID
    episode_number: float | None = None
    episode_title: str | None = None
    air_date: date | None = None
    description: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    runtime_minutes: int | None = None

    model_config = {"from_attributes": True}


class TVSeasonV1Response(BaseModel):
    id: UUID
    series_id: UUID
    season_number: int | None = None
    air_date: date | None = None
    episode_count: int | None = None
    description: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    episodes: list[TVEpisodeV1Response] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TVSeriesV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    description: str | None = None
    original_language: str | None = None
    original_air_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    season_count: int | None = None
    episode_count: int | None = None
    network: str | None = None
    kind: ItemKind = ItemKind.tv
    seasons: list[TVSeasonV1Response] = Field(default_factory=list)
    media: list[TVReleaseMediaResponse] = Field(default_factory=list)
    contributions: list[TVContributorResponse] = Field(default_factory=list)
    identifiers: list[TVIdentifierResponse] = Field(default_factory=list)
    character_appearances: list[TVCharacterResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
