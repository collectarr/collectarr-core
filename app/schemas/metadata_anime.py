from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ItemKind
from app.schemas.metadata_shared import (
    ContributorResponse,
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


class AnimeReleaseMediaResponse(BaseModel):
    id: UUID
    release_id: UUID
    media_number: int
    media_type: str
    title: str | None = None
    episode_count: int | None = None
    runtime_minutes: int | None = None
    region_code: str | None = None
    encoding: str | None = None
    aspect_ratio: str | None = None
    audio_tracks: str | None = None
    subtitles: str | None = None
    resolution: str | None = None
    hdr_format: str | None = None

    model_config = {"from_attributes": True}


class AnimeReleaseEpisodeMapV1Response(BaseModel):
    id: UUID
    release_id: UUID
    media_id: UUID
    episode_id: UUID
    disc_number: int | None = None
    sequence_number: int | None = None

    model_config = {"from_attributes": True}


class AnimeReleaseV1Response(BaseModel):
    id: UUID
    work_id: UUID
    title: str
    sort_title: str | None = None
    description: str | None = None
    media_count: int | None = None
    format: str | None = None
    region_code: str | None = None
    release_date: date | None = None
    publisher: str | None = None
    distributor: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    packaging: str | None = None
    release_status: str | None = None
    language_audio: list[str] | None = None
    language_subtitles: list[str] | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    media: list[AnimeReleaseMediaResponse] = Field(default_factory=list)
    episode_mappings: list[AnimeReleaseEpisodeMapV1Response] = Field(default_factory=list)

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
    releases: list[AnimeReleaseV1Response] = Field(default_factory=list)

    model_config = {"from_attributes": True}
