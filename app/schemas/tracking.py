from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ItemKind


class TrackingSourceType(StrEnum):
    physical = "physical"
    digital = "digital"
    streaming = "streaming"


class TrackingCountResponse(BaseModel):
    key: str
    count: int


class TrackingKindCountResponse(BaseModel):
    kind: ItemKind
    count: int


class TrackingPeriodCountResponse(BaseModel):
    period: str
    count: int


class TrackingEntryUpsertRequest(BaseModel):
    item_id: UUID
    edition_id: UUID | None = None
    variant_id: UUID | None = None
    source_type: TrackingSourceType | None = None
    status: str | None = Field(default=None, min_length=1, max_length=64)
    rating: int | None = Field(default=None, ge=0, le=10)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress_current: int | None = Field(default=None, ge=0)
    progress_total: int | None = Field(default=None, ge=1)
    times_completed: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)
    season_number: int | None = Field(default=None, ge=0)
    episode_number: int | None = Field(default=None, ge=0)


class TrackingEntryResponse(BaseModel):
    id: UUID
    user_id: UUID
    item_id: UUID
    item_title: str
    kind: ItemKind
    edition_id: UUID | None = None
    variant_id: UUID | None = None
    source_type: TrackingSourceType | None = None
    status: str | None = None
    rating: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    times_completed: int | None = None
    notes: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class TrackingTopItemResponse(BaseModel):
    item_id: UUID
    title: str
    kind: ItemKind
    count: int


class TrackingItemStatsResponse(BaseModel):
    item_id: UUID
    item_title: str
    kind: ItemKind
    total_entries: int
    unique_users: int
    average_rating: float | None = None
    rating_count: int
    counts_by_status: list[TrackingCountResponse] = Field(default_factory=list)
    counts_by_source_type: list[TrackingCountResponse] = Field(default_factory=list)
    current_user_entry: TrackingEntryResponse | None = None


class TrackingDashboardResponse(BaseModel):
    total_entries: int
    average_rating: float | None = None
    rating_count: int
    counts_by_status: list[TrackingCountResponse] = Field(default_factory=list)
    counts_by_kind: list[TrackingKindCountResponse] = Field(default_factory=list)
    counts_by_source_type: list[TrackingCountResponse] = Field(default_factory=list)
    recent_entries: list[TrackingEntryResponse] = Field(default_factory=list)


class TrackingFacetsResponse(BaseModel):
    counts_by_status: list[TrackingCountResponse] = Field(default_factory=list)
    counts_by_kind: list[TrackingKindCountResponse] = Field(default_factory=list)
    counts_by_source_type: list[TrackingCountResponse] = Field(default_factory=list)
    counts_by_period: list[TrackingPeriodCountResponse] = Field(default_factory=list)


class AdminTrackingStatsResponse(BaseModel):
    total_entries: int
    unique_users: int
    unique_items: int
    average_rating: float | None = None
    rating_count: int
    counts_by_status: list[TrackingCountResponse] = Field(default_factory=list)
    counts_by_kind: list[TrackingKindCountResponse] = Field(default_factory=list)
    counts_by_source_type: list[TrackingCountResponse] = Field(default_factory=list)
    top_items: list[TrackingTopItemResponse] = Field(default_factory=list)