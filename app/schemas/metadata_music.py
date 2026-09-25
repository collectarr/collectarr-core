from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind
from app.models.partial_date import PartialDateValue
from app.schemas.metadata_shared import ContributorResponse


class MusicContributorResponse(ContributorResponse):
    role_id: str | None = None


class MusicArtistCreditResponse(BaseModel):
    id: UUID
    artist_id: UUID | None = None
    credited_name: str
    join_phrase: str | None = None
    sequence: int | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class MusicReleaseLabelResponse(BaseModel):
    id: UUID
    label_id: UUID | None = None
    label_name: str
    catalog_number: str | None = None
    sequence: int | None = None
    source: str | None = None

    model_config = {"from_attributes": True}


class MusicIdentifierResponse(BaseModel):
    id: UUID
    identifier_type: str
    value: str
    normalized_value: str
    is_primary: bool
    source_provider: ExternalProvider | None = None


class MusicTrackV1Response(BaseModel):
    id: UUID
    medium_id: UUID
    position: str
    title: str
    artist: str | None = None
    is_header: bool = False
    indent_level: int = 0
    parent_header_id: str | None = None
    duration_ms: int | None = None
    offset_ms: int | None = None
    bitrate_kbps: int | None = None
    file_size_bytes: int | None = None
    track_hash: str | None = None
    recording_id: str | None = None
    instrument: str | None = None
    composition: str | None = None

    model_config = {"from_attributes": True}

class MusicMediumV1Response(BaseModel):
    id: UUID
    release_id: UUID
    medium_number: int
    medium_type: str | None = None
    title: str | None = None
    track_count: int | None = None
    expected_track_count: int | None = None
    missing_track_count: int | None = None
    missing_track_positions: list[str] = Field(default_factory=list)
    toc: str | None = None
    cddb_id: str | None = None
    leadout_offset: int | None = None
    bp_disc_id: str | None = None
    sound_type: str | None = None
    vinyl_color: str | None = None
    vinyl_weight: str | None = None
    rpm: int | None = None
    spars: str | None = None
    tracks: list[MusicTrackV1Response] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MusicReleaseSummaryV1Response(BaseModel):
    id: UUID
    release_group_id: UUID
    title: str
    release_date: date | None = None
    release_date_parts: PartialDateValue | None = None
    release_type: str | None = None
    release_status: str | None = None
    medium_types: list[str] = Field(default_factory=list)
    publisher: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    cover_image_url: str | None = None

    model_config = {"from_attributes": True}


class MusicReleaseGroupV1Response(BaseModel):
    id: UUID
    title: str
    sort_title: str | None = None
    original_title: str | None = None
    artist: str | None = None
    original_release_date: date | None = None
    original_release_date_parts: PartialDateValue | None = None
    recording_date: date | None = None
    recording_date_parts: PartialDateValue | None = None
    studio: str | None = None
    is_live: bool | None = None
    genres: list[str] = Field(default_factory=list)
    artist_credits: list[MusicArtistCreditResponse] = Field(default_factory=list)
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    external_links: list[dict[str, Any]] = Field(default_factory=list)
    releases: list[MusicReleaseSummaryV1Response] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MusicReleaseV1Response(BaseModel):
    id: UUID
    release_group_id: UUID
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    release_type: str | None = None
    release_status: str | None = None
    release_date: date | None = None
    release_date_parts: PartialDateValue | None = None
    publisher: str | None = None
    upc: str | None = None
    catalog_number: str | None = None
    barcode: str | None = None
    country_code: str | None = None
    language: str | None = None
    packaging: str | None = None
    cover_image_url: str | None = None
    cover_image_key: str | None = None
    kind: ItemKind = ItemKind.music
    mediums: list[MusicMediumV1Response] = Field(default_factory=list)
    contributions: list[MusicContributorResponse] = Field(default_factory=list)
    artist_credits: list[MusicArtistCreditResponse] = Field(default_factory=list)
    labels: list[MusicReleaseLabelResponse] = Field(default_factory=list)
    identifiers: list[MusicIdentifierResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
