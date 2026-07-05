from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind
from app.schemas.metadata_shared import (
    ContributorResponse,
)


class MusicContributorResponse(ContributorResponse):
    role_id: str | None = None


class MusicIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool
    source_provider: ExternalProvider | None = None


class MusicTrackV1Response(BaseModel):
    id: UUID
    media_id: UUID
    position: str
    title: str
    duration_ms: int | None = None
    offset_ms: int | None = None
    bitrate_kbps: int | None = None
    file_size_bytes: int | None = None
    track_hash: str | None = None
    instrument: str | None = None
    composition: str | None = None

    model_config = {"from_attributes": True}


class MusicMediaV1Response(BaseModel):
    id: UUID
    release_id: UUID
    media_number: int
    media_type: str | None = None
    title: str | None = None
    track_count: int | None = None
    expected_track_count: int | None = None
    missing_track_count: int | None = None
    missing_track_positions: list[str] = Field(default_factory=list)
    toc: str | None = None
    cddb_id: str | None = None
    leadout_offset: int | None = None
    bp_disc_id: str | None = None
    packaging: str | None = None
    media_condition: str | None = None
    sound_type: str | None = None
    vinyl_color: str | None = None
    vinyl_weight: str | None = None
    rpm: int | None = None
    spars: str | None = None
    tracks: list[MusicTrackV1Response] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MusicReleaseV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    release_type: str | None = None
    release_status: str | None = None
    release_date: date | None = None
    recording_date: date | None = None
    track_count: int | None = None
    expected_media_count: int | None = None
    missing_media_count: int | None = None
    missing_disc_numbers: list[int] = Field(default_factory=list)
    publisher: str | None = None
    studio: str | None = None
    upc: str | None = None
    catalog_number: str | None = None
    barcode: str | None = None
    country_code: str | None = None
    language: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    extras: str | None = None
    kind: ItemKind = ItemKind.music
    media: list[MusicMediaV1Response] = Field(default_factory=list)
    contributions: list[MusicContributorResponse] = Field(default_factory=list)
    identifiers: list[MusicIdentifierResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
