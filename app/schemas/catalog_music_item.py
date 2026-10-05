"""Wire schemas for flattened Music catalog items."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    model_config = ConfigDict(from_attributes=True)

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
    matrix_number_side_a: str | None = None
    matrix_number_side_b: str | None = None
    tracks: list[CatalogMusicTrackResponse]

    model_config = ConfigDict(from_attributes=True)

    @field_validator("tracks")
    @classmethod
    def validate_track_identity(cls, tracks: list[CatalogMusicTrackResponse]) -> list[CatalogMusicTrackResponse]:
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
                    level: header for level, header in active_headers.items()
                    if level < track.indent_level
                }
                active_headers[track.indent_level] = track
        return ordered


def normalize_music_discs(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build validated JSON-safe discs, preserving supplied component IDs."""
    discs: list[CatalogMusicDiscResponse] = []
    for raw in value:
        tracks: list[CatalogMusicTrackResponse] = []
        for index, track in enumerate(raw.get("tracks") or []):
            position_order = track.get("position_order")
            if not isinstance(position_order, int) or isinstance(position_order, bool):
                position_order = index
            position = track.get("position")
            if track.get("is_header") is True:
                position = "" if position is None else str(position)
            elif position is None or not str(position).strip():
                position = str(position_order + 1)
            tracks.append(
                CatalogMusicTrackResponse.model_validate(
                    {
                        **track,
                        "id": track.get("id") or uuid4(),
                        "position": str(position),
                        "position_order": position_order,
                    }
                )
            )
        discs.append(CatalogMusicDiscResponse.model_validate({
            **raw, "id": raw.get("id") or uuid4(), "tracks": tracks,
        }))
    if len({disc.disc_number for disc in discs}) != len(discs):
        raise ValueError("Disc numbers must be unique within an album")
    if len({disc.id for disc in discs}) != len(discs):
        raise ValueError("Disc IDs must be unique within an album")
    track_ids = [track.id for disc in discs for track in disc.tracks]
    if len(set(track_ids)) != len(track_ids):
        raise ValueError("Track IDs must be unique within an album")
    return [disc.model_dump(mode="json") for disc in sorted(discs, key=lambda disc: disc.disc_number)]


class CatalogMusicItemResponse(BaseModel):
    id: UUID
    kind: str = "music"
    title: str
    sort_title: str | None = None
    subtitle: str | None = None
    artist: str | None = None
    artist_credits: list[dict[str, Any]]
    original_release_date: date | None = None
    original_release_date_parts: dict[str, int] | str | None = None
    recording_date: date | None = None
    recording_date_parts: dict[str, int] | str | None = None
    release_date: date | None = None
    release_date_parts: dict[str, int] | str | None = None
    label: str | None = None
    format: str | None = None
    barcode: str | None = None
    catalog_number: str | None = None
    genres: list[str]
    packaging: str | None = None
    studios: list[str]
    country: str | None = None
    is_live: bool | None = None
    sound_types: list[str]
    vinyl_color: str | None = None
    vinyl_weight: str | None = None
    rpm: int | None = None
    extra: str | None = None
    spars: str | None = None
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

    model_config = ConfigDict(from_attributes=True)
