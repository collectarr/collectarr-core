from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import UserRole


class CanonicalCatalogWriteResponse(BaseModel):
    """Result of a source-neutral write into the canonical catalog."""

    item_id: UUID
    kind: str
    created: bool
    item: object | None = None


class AdminDeleteResponse(BaseModel):
    deleted: bool


class AdminCatalogSummaryResponse(BaseModel):
    items: int
    items_by_kind: dict[str, int] = Field(default_factory=dict)
    image_assets: int
    image_cache_entries: int
    missing_cover_items: int
    duplicate_candidate_groups: int


class AdminCatalogItemIntegritySample(BaseModel):
    item_id: UUID
    kind: str
    issues: list[str] = Field(default_factory=list)
    detail_keys: list[str] = Field(default_factory=list)


class AdminCatalogItemIntegrityResponse(BaseModel):
    scan_limit: int | None = None
    scan_limited: bool = False
    scanned_items: int = 0
    invalid_items: int = 0
    issue_counts: dict[str, int] = Field(default_factory=dict)
    samples: list[AdminCatalogItemIntegritySample] = Field(default_factory=list)


class AdminSearchStatusResponse(BaseModel):
    ok: bool
    index_name: str
    document_count: int | None = None
    is_empty: bool | None = None
    error: str | None = None


class AdminSearchReindexResponse(BaseModel):
    ok: bool
    index_name: str
    indexed_documents: int
    error: str | None = None


class AdminSearchHistoryEntry(BaseModel):
    timestamp: datetime
    ok: bool
    index_name: str
    indexed_documents: int
    error: str | None = None


class AdminAuditLogResponse(BaseModel):
    id: UUID
    action: str
    actor_user_id: UUID | None = None
    actor_email: str | None = None
    entity_type: str
    entity_id: UUID | None = None
    details_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminDuplicateCandidateResponse(BaseModel):
    kind: str
    title: str
    item_number: str | None
    count: int
    item_ids: list[UUID]
    reason: str = "same title and item number"
    has_cover_conflicts: bool = False
    duplicate_score: int = 0
    recommended_target_item_id: UUID | None = None
    confidence_factors: list[str] = Field(default_factory=list)
    merge_warnings: list[str] = Field(default_factory=list)


class AdminDuplicateQueueSummaryResponse(BaseModel):
    pending_candidates: int
    merged_reviews: int
    ignored_reviews: int
    total_reviews: int
    latest_review_at: datetime | None = None


class AdminDuplicateReviewEntryResponse(BaseModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: UUID | None = None
    entity_ids: list[str] = Field(default_factory=list)
    ignore_token: str | None = None
    target_entity_id: UUID | None = None
    source_entity_ids: list[str] | None = None
    duplicate_score: int | None = None
    actor_user_id: UUID | None = None
    actor_email: str | None = None
    note: str | None = None
    details_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminDuplicateIgnoreRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=2, max_length=50)


class AdminDuplicateActionResponse(BaseModel):
    ok: bool
    affected_items: int


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    is_active: bool
    role: UserRole
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    display_name: str | None = None


class ImageCacheStatsResponse(BaseModel):
    total_entries: int
    total_size_bytes: int
    max_size_bytes: int
    usage_percent: float
    cache_enabled: bool


class ImageCachePurgeResponse(BaseModel):
    deleted_entries: int
    freed_bytes: int
