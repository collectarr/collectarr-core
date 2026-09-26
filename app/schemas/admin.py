from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ItemKind, UserRole
from app.models.partial_date import PartialDateValue


class CanonicalCatalogWriteResponse(BaseModel):
    """Result of a source-neutral write into the canonical catalog."""

    item_id: UUID
    kind: str
    created: bool
    item: object | None = None


class AdminDeleteResponse(BaseModel):
    deleted: bool


class AdminMetadataCreditInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=64)


class AdminMetadataCorrectionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    title_extension: str | None = Field(default=None, max_length=255)
    sort_key: str | None = Field(default=None, max_length=255)
    original_title: str | None = Field(default=None, max_length=255)
    localized_title: str | None = Field(default=None, max_length=255)
    search_aliases: list[str] | None = None
    item_number: str | None = Field(default=None, max_length=64)
    synopsis: str | None = None
    crossover: str | None = Field(default=None, max_length=255)
    plot_summary: str | None = None
    plot_description: str | None = None
    edition_title: str | None = Field(default=None, max_length=255)
    page_count: int | None = Field(default=None, ge=0)
    runtime_minutes: int | None = Field(default=None, ge=0)
    publisher: str | None = Field(default=None, max_length=255)
    release_date: PartialDateValue | date | None = None
    imprint: str | None = Field(default=None, max_length=255)
    subtitle: str | None = Field(default=None, max_length=255)
    series_group: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=32)
    age_rating: str | None = Field(default=None, max_length=64)
    audience_rating: str | None = Field(default=None, max_length=32)
    genres: list[str] | None = None
    platforms: list[str] | None = None
    identifiers: list[str] | None = None
    company_roles: list[str] | None = None
    age_ratings: list[str] | None = None
    contributors: list[str] | None = None
    mechanics: list[str] | None = None
    categories: list[str] | None = None
    families: list[str] | None = None
    expansions: list[str] | None = None
    rankings: list[str] | None = None
    tracks: list[dict[str, Any]] | None = None
    creators: list[AdminMetadataCreditInput] | None = None
    characters: list[str] | None = None
    story_arcs: list[str] | None = None
    color: str | None = Field(default=None, max_length=64)
    nr_discs: int | None = Field(default=None, ge=0)
    screen_ratio: str | None = Field(default=None, max_length=64)
    audio_tracks: str | None = Field(default=None, max_length=255)
    subtitles: str | None = Field(default=None, max_length=255)
    layers: str | None = Field(default=None, max_length=64)
    trailer_urls: list[dict[str, Any]] | None = None
    external_links: list[dict[str, Any]] | None = None
    catalog_number: str | None = Field(default=None, max_length=100)
    release_status: str | None = Field(default=None, max_length=64)
    physical_format: str | None = Field(default=None, max_length=64)
    variant_name: str | None = Field(default=None, max_length=255)
    barcode: str | None = Field(default=None, max_length=32)
    cover_image_url: str | None = Field(default=None, max_length=1024)
    thumbnail_image_url: str | None = Field(default=None, max_length=1024)

    model_config = {"extra": "forbid"}


class AdminBundleReleaseMemberUpdateRequest(BaseModel):
    id: UUID | None = None
    item_id: UUID | None = None
    role: str = Field(min_length=1, max_length=32)
    sequence_number: int | None = Field(default=None, ge=1)
    disc_number: int | None = Field(default=None, ge=1)
    disc_label: str | None = Field(default=None, max_length=255)
    quantity: int = Field(default=1, ge=1)
    is_primary: bool = False


class AdminBundleReleaseCorrectionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    bundle_type: str | None = Field(default=None, max_length=64)
    format: str | None = Field(default=None, max_length=64)
    variant_type: str | None = Field(default=None, max_length=64)
    packaging_type: str | None = Field(default=None, max_length=64)
    region: str | None = Field(default=None, max_length=32)
    language: str | None = Field(default=None, max_length=32)
    publisher: str | None = Field(default=None, max_length=255)
    sku: str | None = Field(default=None, max_length=100)
    barcode: str | None = Field(default=None, max_length=32)
    release_date: PartialDateValue | date | None = None
    release_date_parts: PartialDateValue | None = None
    cover_image_url: str | None = Field(default=None, max_length=1024)
    thumbnail_image_url: str | None = Field(default=None, max_length=1024)
    members: list[AdminBundleReleaseMemberUpdateRequest] | None = None


class AdminCatalogSummaryResponse(BaseModel):
    items: int
    items_by_kind: dict[str, int] = Field(default_factory=dict)
    series: int
    volumes: int
    editions: int
    variants: int
    image_assets: int
    image_cache_entries: int
    missing_cover_items: int
    duplicate_candidate_groups: int


class AdminNormalizedMetadataDriftSample(BaseModel):
    entity_type: str
    entity_id: UUID
    kind: ItemKind
    issues: list[str] = Field(default_factory=list)
    normalized_keys: list[str] = Field(default_factory=list)


class AdminNormalizedMetadataDriftReportResponse(BaseModel):
    expected_schema_version: int
    scan_limit: int | None = None
    scan_limited: bool = False
    scanned_entities: int = 0
    entities_with_normalized: int = 0
    drifted_entities: int = 0
    typed_scanned_items: int = 0
    typed_drifted_items: int = 0
    schema_issue_count: int = 0
    blocking_issue_count: int = 0
    release_gate_ok: bool = True
    issue_counts: dict[str, int] = Field(default_factory=dict)
    samples: list[AdminNormalizedMetadataDriftSample] = Field(default_factory=list)


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


class AdminDuplicateMergeRequest(BaseModel):
    target_item_id: UUID
    source_item_ids: list[UUID] = Field(min_length=1, max_length=49)


class AdminDuplicateReviewRequest(BaseModel):
    decision: str = Field(pattern="^(ignore|merge)$")
    item_ids: list[UUID] = Field(default_factory=list, max_length=50)
    target_item_id: UUID | None = None
    source_item_ids: list[UUID] = Field(default_factory=list, max_length=49)
    note: str | None = Field(default=None, max_length=1000)


class AdminDuplicateActionResponse(BaseModel):
    ok: bool
    affected_items: int
    item: dict[str, Any] | None = None


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
