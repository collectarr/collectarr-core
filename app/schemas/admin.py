from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind, UserRole
from app.schemas.metadata import ItemResponse


class ProviderStatusResponse(BaseModel):
    name: str
    display_name: str
    kind: str
    supported_kinds: list[str] = Field(default_factory=list)
    status: str
    is_configured: bool
    supports_search: bool = True
    supports_ingest: bool = True
    requires_user_key: bool = False
    non_commercial_only: bool = False
    allows_redistribution: bool = False
    allows_image_mirroring: bool = False
    requires_attribution: bool = False
    license_name: str | None = None
    terms_url: str | None = None
    attribution_url: str | None = None
    rate_limit: str | None = None
    cache_policy: str | None = None
    message: str


class ProviderStatusListResponse(BaseModel):
    contract_version: int
    providers: list[ProviderStatusResponse]


class ProviderIngestRequest(BaseModel):
    provider: ExternalProvider
    provider_item_id: str = Field(min_length=1, max_length=255)


class ProviderSearchRequest(BaseModel):
    provider: ExternalProvider
    query: str = Field(min_length=1, max_length=255)
    kind: ItemKind | None = None


class ProviderIngestResponse(BaseModel):
    item_id: UUID
    created: bool
    item: ItemResponse


class ProviderPreviewCredit(BaseModel):
    name: str
    role: str | None = None


class ProviderPreviewTrack(BaseModel):
    position: int | None = None
    title: str
    duration_seconds: int | None = None
    artist: str | None = None
    disc_number: int | None = None


class ProviderPreviewResponse(BaseModel):
    """Normalized provider data returned WITHOUT creating anything in the DB."""

    provider: str
    provider_item_id: str
    kind: ItemKind
    title: str
    item_number: str | None = None
    synopsis: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    volume_number: int | None = None
    volume_start_year: int | None = None
    publisher: str | None = None
    imprint: str | None = None
    edition_title: str | None = None
    edition_format: str | None = None
    physical_format: str | None = None
    physical_format_label: str | None = None
    release_date: date | None = None
    barcode: str | None = None
    isbn: str | None = None
    variant_name: str | None = None
    cover_image_url: str | None = None
    cover_price_cents: int | None = None
    currency: str | None = None
    country: str | None = None
    language: str | None = None
    age_rating: str | None = None
    subtitle: str | None = None
    series_group: str | None = None
    page_count: int | None = None
    runtime_minutes: int | None = None
    track_count: int | None = None
    creators: list[ProviderPreviewCredit] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    story_arcs: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    tracks: list[ProviderPreviewTrack] = Field(default_factory=list)


class ProviderIngestHistoryEntry(BaseModel):
    id: int
    timestamp: datetime
    provider: ExternalProvider
    provider_item_id: str
    status: str
    attempts: int
    item_id: UUID | None = None
    error: str | None = None


class ProviderIngestRetryRequest(BaseModel):
    history_id: int


class ProviderIngestJobCreateRequest(BaseModel):
    provider: ExternalProvider
    provider_item_id: str = Field(min_length=1, max_length=255)
    max_attempts: int = Field(default=3, ge=1, le=10)


class ProviderIngestJobResponse(BaseModel):
    id: UUID
    provider: ExternalProvider
    provider_item_id: str
    status: str
    attempts: int
    max_attempts: int
    next_run_at: datetime | None = None
    item_id: UUID | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderIngestJobRunResponse(BaseModel):
    processed: int
    jobs: list[ProviderIngestJobResponse]
    recovered: int = 0


class ProviderIngestJobSummaryResponse(BaseModel):
    queued: int = 0
    running: int = 0
    failed: int = 0
    done: int = 0
    due_queued: int = 0
    stale_running: int = 0
    oldest_queued_at: datetime | None = None
    next_run_at: datetime | None = None
    latest_failure_at: datetime | None = None


class AdminMetadataCorrectionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    item_number: str | None = Field(default=None, max_length=64)
    synopsis: str | None = None
    page_count: int | None = Field(default=None, ge=0)
    publisher: str | None = Field(default=None, max_length=255)
    release_date: date | None = None
    physical_format: str | None = Field(default=None, max_length=64)
    variant_name: str | None = Field(default=None, max_length=255)
    barcode: str | None = Field(default=None, max_length=32)
    cover_image_url: str | None = Field(default=None, max_length=1024)
    thumbnail_image_url: str | None = Field(default=None, max_length=1024)


class AdminCatalogSummaryResponse(BaseModel):
    items: int
    series: int
    volumes: int
    editions: int
    variants: int
    releases: int
    provider_links: int
    image_assets: int
    image_cache_entries: int
    pending_proposals: int
    missing_cover_items: int
    missing_provider_link_items: int
    duplicate_candidate_groups: int
    provider_ingest_successes: int = 0
    provider_ingest_failures: int = 0


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
    has_provider_conflicts: bool = False
    has_cover_conflicts: bool = False


class AdminDuplicateIgnoreRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=2, max_length=50)


class AdminDuplicateMergeRequest(BaseModel):
    target_item_id: UUID
    source_item_ids: list[UUID] = Field(min_length=1, max_length=49)


class AdminDuplicateActionResponse(BaseModel):
    ok: bool
    affected_items: int
    item: ItemResponse | None = None


class MetadataProposalSummaryResponse(BaseModel):
    pending: int
    approved: int
    rejected: int
    total: int


class MetadataProposalAdminResponse(BaseModel):
    id: UUID
    provider: ExternalProvider
    provider_item_id: str | None
    query: str
    title: str | None
    summary: str | None
    image_url: str | None
    status: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    is_active: bool
    is_admin: bool
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
    mirroring_enabled: bool
    providers: dict[str, int] = Field(default_factory=dict, description="Entry count per provider")


class ImageCachePurgeResponse(BaseModel):
    deleted_entries: int
    freed_bytes: int
