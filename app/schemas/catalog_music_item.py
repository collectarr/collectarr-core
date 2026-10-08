"""Wire schemas for flattened Music catalog items."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from app.models.partial_date import PartialDateValue
from app.schemas.catalog_item_base import CatalogItemBaseResponse
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
    position: str = Field(max_length=16, strict=True)
    position_order: int = Field(ge=0, strict=True)
    title: str = Field(min_length=1, max_length=255, strict=True)
    artist: str | None = Field(default=None, strict=True)
    duration_ms: int | None = Field(default=None, ge=0, strict=True)
    is_header: bool = Field(strict=True)
    parent_header_id: UUID | None = None
    indent_level: int = Field(ge=0, le=8, strict=True)

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("title")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value or value != value.strip():
            raise ValueError("Track title must be non-empty trimmed text")
        return value

    @model_validator(mode="after")
    def validate_row_type(self) -> CatalogMusicTrackResponse:
        if self.position != self.position.strip():
            raise ValueError("Track position must be trimmed text")
        if self.is_header:
            if self.position or self.artist is not None or self.duration_ms is not None:
                raise ValueError("Headers must not have a position, artist, or duration")
        elif not self.position:
            raise ValueError("Track position must not be empty")
        return self


class CatalogMusicDiscResponse(BaseModel):
    id: UUID
    disc_number: int = Field(ge=1, strict=True)
    title: str | None = None
    format_family: MusicDiscFormatFamily | None = None
    format: str | None = None
    sound_types: list[StrictStr]
    color: str | None = None
    vinyl_weight_grams: int | None = Field(default=None, gt=0, strict=True)
    rpm: str | None = None
    matrix_number: str | None = None
    matrix_number_side_a: str | None = None
    matrix_number_side_b: str | None = None
    tracks: list[CatalogMusicTrackResponse]

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator(
        "title",
        "format",
        "color",
        "rpm",
        "matrix_number",
        "matrix_number_side_a",
        "matrix_number_side_b",
    )
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value or value != value.strip():
            raise ValueError("Optional Music disc text must be non-empty and trimmed")
        return value

    @field_validator("tracks")
    @classmethod
    def validate_track_identity(
        cls, tracks: list[CatalogMusicTrackResponse]
    ) -> list[CatalogMusicTrackResponse]:
        if len({track.id for track in tracks}) != len(tracks):
            raise ValueError("Track IDs must be unique within a disc")
        if len({track.position_order for track in tracks}) != len(tracks):
            raise ValueError("Track order must be unique within a disc")
        ordered = sorted(tracks, key=lambda track: track.position_order)
        if [track.position_order for track in tracks] != [
            track.position_order for track in ordered
        ]:
            raise ValueError("Tracks must be ordered by position_order")
        playable = [track for track in tracks if not track.is_header]
        if len({track.position.casefold() for track in playable}) != len(playable):
            raise ValueError("Track positions must be unique within a disc")
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
        return tracks

    @field_validator("sound_types")
    @classmethod
    def validate_sound_types(cls, values: list[str]) -> list[str]:
        if any(not value or value != value.strip() for value in values):
            raise ValueError("Music disc sound_types must be non-empty trimmed text")
        return values

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
    """Validate canonical discs without reordering or inventing component data."""
    discs: list[CatalogMusicDiscResponse] = []
    for raw in value:
        discs.append(CatalogMusicDiscResponse.model_validate(raw))
    if len({disc.disc_number for disc in discs}) != len(discs):
        raise ValueError("Disc numbers must be unique within an album")
    if [disc.disc_number for disc in discs] != sorted(disc.disc_number for disc in discs):
        raise ValueError("Discs must be ordered by disc_number")
    if len({disc.id for disc in discs}) != len(discs):
        raise ValueError("Disc IDs must be unique within an album")
    track_ids = [track.id for disc in discs for track in disc.tracks]
    if len(set(track_ids)) != len(track_ids):
        raise ValueError("Track IDs must be unique within an album")
    return [disc.model_dump(mode="json", exclude_unset=True) for disc in discs]


class CatalogMusicArtistCreditResponse(BaseModel):
    id: str = Field(min_length=1, strict=True)
    name: str = Field(min_length=1, strict=True)
    sort_name: str | None = Field(default=None, strict=True)
    artist_id: str | None = Field(default=None, strict=True)
    sequence: int = Field(ge=1, strict=True)
    join_phrase: str | None = Field(default=None, strict=True)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id", "name", "sort_name", "artist_id")
    @classmethod
    def validate_credit_text(cls, value: str | None) -> str | None:
        if value is not None and (not value or value != value.strip()):
            raise ValueError("Music artist credit text must be non-empty trimmed text")
        return value


class CatalogMusicRoleCreditResponse(BaseModel):
    id: str = Field(min_length=1, strict=True)
    name: str = Field(min_length=1, strict=True)
    person_id: str = Field(min_length=1, strict=True)
    role_id: str | None = Field(default=None, strict=True)
    sequence: int = Field(ge=1, strict=True)
    sort_name: str | None = Field(default=None, strict=True)
    image_url: str | None = Field(default=None, strict=True)
    instrument: str | None = Field(default=None, strict=True)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id", "name", "person_id", "role_id", "sort_name", "image_url", "instrument")
    @classmethod
    def validate_credit_text(cls, value: str | None) -> str | None:
        if value is not None and (not value or value != value.strip()):
            raise ValueError("Music role credit text must be non-empty trimmed text")
        return value


class CatalogMusicExternalLinkResponse(BaseModel):
    url: str = Field(min_length=1, strict=True)
    title: str | None = Field(default=None, strict=True)
    description: str | None = Field(default=None, strict=True)

    model_config = ConfigDict(extra="forbid")

    @field_validator("url", "title", "description")
    @classmethod
    def validate_link_text(cls, value: str | None) -> str | None:
        if value is not None and (not value or value != value.strip()):
            raise ValueError("Music external link text must be non-empty trimmed text")
        return value


class CatalogMusicItemResponse(CatalogItemBaseResponse):
    kind: str = "music"
    sort_title: str | None = None
    subtitle: str | None = None
    artist: str | None = None
    artist_credits: list[CatalogMusicArtistCreditResponse]
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
    composers: list[CatalogMusicRoleCreditResponse]
    conductors: list[CatalogMusicRoleCreditResponse]
    choruses: list[str]
    compositions: list[str]
    orchestras: list[str]
    songwriters: list[CatalogMusicRoleCreditResponse]
    producers: list[CatalogMusicRoleCreditResponse]
    engineers: list[CatalogMusicRoleCreditResponse]
    musicians: list[CatalogMusicRoleCreditResponse]
    external_links: list[CatalogMusicExternalLinkResponse]
    cover_image_url: str | None = None
    back_cover_image_url: str | None = None
    thumbnail_image_url: str | None = None
    discs: list[CatalogMusicDiscResponse]

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CatalogMusicItemSearchPage(CatalogItemPage[CatalogMusicItemResponse]):
    """A stable page of detailed Music Catalog Item search results."""
