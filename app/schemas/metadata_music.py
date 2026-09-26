from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.partial_date import PartialDateValue


class MusicAlbumArtistV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=500)
    sort_name: str | None = Field(default=None, max_length=500)


class MusicAlbumLabelV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    catalog_number: str | None = Field(default=None, max_length=100)


class MusicAlbumDiscTitleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disc_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)


class MusicAlbumTrackV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    album_id: UUID
    disc_number: int = Field(ge=1)
    position: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    artist: str | None = Field(default=None, max_length=500)
    duration_ms: int | None = Field(default=None, ge=0)


class MusicAlbumTrackInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disc_number: int = Field(ge=1)
    position: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    artist: str | None = Field(default=None, max_length=500)
    duration_ms: int | None = Field(default=None, ge=0)


class MusicAlbumCreditV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=64)
    sequence: int = Field(ge=0)
    credited_name: str = Field(min_length=1, max_length=500)
    join_phrase: str | None = Field(default=None, max_length=100)
    instrument: str | None = Field(default=None, max_length=100)


class MusicAlbumLinkV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int = Field(ge=0)
    url: HttpUrl
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class MusicAlbumWriteV1(BaseModel):
    """Source-neutral canonical Music album data accepted by create/update."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    sort_title: str | None = Field(default=None, max_length=255)
    subtitle: str | None = Field(default=None, max_length=500)
    artists: list[MusicAlbumArtistV1] = Field(default_factory=list)
    release_date: PartialDateValue | None = None
    original_release_date: PartialDateValue | None = None
    recording_date: PartialDateValue | None = None
    labels: list[MusicAlbumLabelV1] = Field(default_factory=list)
    format: str | None = Field(default=None, max_length=100)
    barcode: str | None = Field(default=None, max_length=100)
    catalog_number: str | None = Field(default=None, max_length=100)
    genres: list[str] = Field(default_factory=list)
    packaging: str | None = Field(default=None, max_length=100)
    studio: list[str] = Field(default_factory=list)
    country: str | None = Field(default=None, max_length=64)
    is_live: bool | None = None
    sound_types: list[str] = Field(default_factory=list)
    vinyl_color: str | None = Field(default=None, max_length=100)
    vinyl_weight: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    rpm: int | None = Field(default=None, ge=0)
    extras: list[str] = Field(default_factory=list)
    spars_code: str | None = Field(default=None, max_length=50)
    box_set: str | None = Field(default=None, max_length=255)
    matrix_number_side_a: str | None = Field(default=None, max_length=255)
    matrix_number_side_b: str | None = Field(default=None, max_length=255)
    cover_image_url: HttpUrl | None = None
    back_cover_image_url: HttpUrl | None = None
    disc_titles: list[MusicAlbumDiscTitleV1] = Field(default_factory=list)
    tracks: list[MusicAlbumTrackInputV1] = Field(default_factory=list)
    credits: list[MusicAlbumCreditV1] = Field(default_factory=list)
    links: list[MusicAlbumLinkV1] = Field(default_factory=list)


class MusicAlbumV1Response(MusicAlbumWriteV1):
    id: UUID
    tracks: list[MusicAlbumTrackV1] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
