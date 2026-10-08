"""Wire schemas for flattened Music catalog items."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.partial_date import PartialDateValue
from app.schemas.metadata_shared import CatalogItemPage


class MusicDiscFormatFamily(str, Enum):
    vinyl = "vinyl"
    cd = "cd"
    sacd = "sacd"
    cassette = "cassette"
    minidisc = "minidisc"
    digital = "digital"
    other = "other"


class CatalogMusicTrackResponse(BaseModel):
    id: UUID
    position: str = Field(default="", max_length=16)
    position_order: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=255)
    artist: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    is_header: bool = False
    parent_header_id: UUID | None = None
    indent_level: int = Field(default=0, ge=0, le=8)

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("title")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Track title must not be empty")
        return value

    @model_validator(mode="after")
    def validate_row_type(self) -> CatalogMusicTrackResponse:
        self.position = self.position.strip()
        if self.is_header:
            if self.position or self.artist is not None or self.duration_ms is not None:
                raise ValueError("Headers must not have a position, artist, or duration")
        elif not self.position:
            raise ValueError("Track position must not be empty")
        return self


class CatalogMusicDiscResponse(BaseModel):
    id: UUID
    disc_number: int = Field(ge=1)
    title: str | None = None
    format_family: MusicDiscFormatFamily | None = None
    format: str | None = None
    sound_types: list[str] = Field(default_factory=list)
    color: str | None = None
    vinyl_weight_grams: int | None = Field(default=None, gt=0)
    rpm: str | None = None
    matrix_number: str | None = None
    matrix_number_side_a: str | None = None
    matrix_number_side_b: str | None = None
    tracks: list[CatalogMusicTrackResponse]

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("rpm", mode="before")
    @classmethod
    def coerce_rpm(cls, value: Any) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s or None

    @field_validator("vinyl_weight_grams", mode="before")
    @classmethod
    def coerce_weight(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            digits = "".join(c for c in value if c.isdigit())
            if not digits:
                return None
            return int(digits)
        return int(value)

    @field_validator(
        "title",
        "format",
        "color",
        "matrix_number",
        "matrix_number_side_a",
        "matrix_number_side_b",
    )
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("tracks")
    @classmethod
    def validate_track_identity(
        cls, tracks: list[CatalogMusicTrackResponse]
    ) -> list[CatalogMusicTrackResponse]:
        if len({track.id for track in tracks}) != len(tracks):
            raise ValueError("Track IDs must be unique within a disc")
        if len({track.position_order for track in tracks}) != len(tracks):
            raise ValueError("Track order must be unique within a disc")
        playable = [track for track in tracks if not track.is_header]
        if len({track.position.casefold() for track in playable}) != len(playable):
            raise ValueError("Track positions must be unique within a disc")
        ordered = sorted(tracks, key=lambda track: track.position_order)
        active_headers: dict[int, CatalogMusicTrackResponse] = {}
        for track in ordered:
            if track.parent_header_id is None:
                if track.indent_level != 0:
                    raise ValueError("Rows without a parent header must have indent_level zero")
            else:
                parent = active_headers.get(track.indent_level - 1)
                if parent is None or parent.id != track.parent_header_id:
                    raise ValueError("Parent must be an active preceding header in the same disc")
            if track.is_header:
                active_headers = {
                    level: header
                    for level, header in active_headers.items()
                    if level < track.indent_level
                }
                active_headers[track.indent_level] = track
        return ordered

    @model_validator(mode="after")
    def validate_disc_semantics(self) -> CatalogMusicDiscResponse:
        if self.vinyl_weight_grams is not None:
            if self.format_family != MusicDiscFormatFamily.vinyl:
                raise ValueError("vinyl_weight_grams is only allowed when format_family is vinyl")
        if self.rpm is not None:
            if self.format_family not in (
                None,
                MusicDiscFormatFamily.vinyl,
                MusicDiscFormatFamily.other,
            ):
                raise ValueError(f"RPM is not allowed for {self.format_family.value} discs")
        if self.matrix_number_side_a is not None or self.matrix_number_side_b is not None:
            if self.format_family in (
                MusicDiscFormatFamily.cd,
                MusicDiscFormatFamily.sacd,
                MusicDiscFormatFamily.minidisc,
                MusicDiscFormatFamily.digital,
            ):
                raise ValueError(
                    f"Side matrix numbers are not allowed for {self.format_family.value} discs"
                )
        return self


def validate_music_discs(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate canonical discs without inventing identities or track data."""
    discs: list[CatalogMusicDiscResponse] = []
    for raw in value:
        discs.append(CatalogMusicDiscResponse.model_validate(raw))
    if len({disc.disc_number for disc in discs}) != len(discs):
        raise ValueError("Disc numbers must be unique within an album")
    if len({disc.id for disc in discs}) != len(discs):
        raise ValueError("Disc IDs must be unique within an album")
    track_ids = [track.id for disc in discs for track in disc.tracks]
    if len(set(track_ids)) != len(track_ids):
        raise ValueError("Track IDs must be unique within an album")
    return [
        disc.model_dump(mode="json") for disc in sorted(discs, key=lambda disc: disc.disc_number)
    ]


class CatalogMusicItemResponse(BaseModel):
    id: UUID
    kind: str = "music"
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    artist: str | None = None
    artist_credits: list[dict[str, Any]]
    original_release_date: PartialDateValue | None = None
    recording_date: PartialDateValue | None = None
    release_date: PartialDateValue | None = None
    label: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    genres: list[str]
    packaging: str | None = None
    studios: list[str]
    country: str | None = None
    is_live: bool | None = None
    extra: list[str]
    spars_code: str | None = None
    box_set: str | None = None
    composers: list[dict[str, Any]]
    conductors: list[dict[str, Any]]
    choruses: list[str]
    compositions: list[str]
    orchestras: list[str]
    songwriters: list[dict[str, Any]]
    producers: list[dict[str, Any]]
    engineers: list[dict[str, Any]]
    musicians: list[dict[str, Any]]
    external_links: list[dict[str, Any]]
    cover_image_url: str | None = None
    back_cover_image_url: str | None = None
    thumbnail_image_url: str | None = None
    revision: int
    discs: list[CatalogMusicDiscResponse]

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogMusicItemSearchPage(CatalogItemPage[CatalogMusicItemResponse]):
    """A stable page of detailed Music Catalog Item search results."""
