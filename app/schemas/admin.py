from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind, UserRole
from app.schemas.metadata import (
    BoardGameWorkV1Response,
    AnimeSeriesV1Response,
    BookWorkV1Response,
    ComicWorkV1Response,
    GameWorkV1Response,
    MangaWorkV1Response,
    MovieWorkV1Response,
    MusicReleaseV1Response,
    TVSeriesV1Response,
)


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


class ProviderCacheStatsResponse(BaseModel):
    hits: int = 0
    misses: int = 0
    writes: int = 0
    entries: int = 0
    backoffs: int = 0
    local_entries: int = 0
    redis_entries: int = 0
    local_backoffs: int = 0
    redis_backoffs: int = 0


class ProviderCacheSummaryResponse(BaseModel):
    search: ProviderCacheStatsResponse
    preview: ProviderCacheStatsResponse


class ProviderStatusListResponse(BaseModel):
    providers: list[ProviderStatusResponse]
    cache_stats: ProviderCacheSummaryResponse


class ProviderIngestRequest(BaseModel):
    provider: ExternalProvider
    provider_item_id: str = Field(min_length=1, max_length=255)
    kind: ItemKind | None = None


class ProviderSearchRequest(BaseModel):
    provider: ExternalProvider
    query: str = Field(min_length=1, max_length=255)
    kind: ItemKind | None = None


class ProviderIngestResponse(BaseModel):
    item_id: UUID
    created: bool
    item: (
        dict[str, Any]
        | BookWorkV1Response
        | ComicWorkV1Response
        | GameWorkV1Response
        | BoardGameWorkV1Response
        | MangaWorkV1Response
        | AnimeSeriesV1Response
        | MovieWorkV1Response
        | MusicReleaseV1Response
        | TVSeriesV1Response
    )


class ProviderPreviewCredit(BaseModel):
    name: str
    role: str | None = None
    image_url: str | None = None


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
    volume_number: float | None = None
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
    audience_rating: str | None = None
    subtitle: str | None = None
    series_group: str | None = None
    page_count: int | None = None
    runtime_minutes: int | None = None
    track_count: int | None = None
    catalog_number: str | None = None
    creators: list[ProviderPreviewCredit] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    story_arcs: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    release_status: str | None = None
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


class AdminReleaseMediaMappingRuleCreateRequest(BaseModel):
    provider: ExternalProvider | None = None
    release_type: str = Field(min_length=1, max_length=64)
    target_kind: ItemKind
    priority: int = Field(default=100, ge=0, le=10000)
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=500)


class AdminReleaseMediaMappingRuleUpdateRequest(BaseModel):
    provider: ExternalProvider | None = None
    release_type: str | None = Field(default=None, min_length=1, max_length=64)
    target_kind: ItemKind | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


class AdminReleaseMediaMappingRuleResponse(BaseModel):
    id: UUID
    provider: ExternalProvider | None = None
    release_type: str
    target_kind: ItemKind
    priority: int
    is_active: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminProviderPrefillResolveRequest(BaseModel):
    source: str = Field(pattern="^(proposal|ingest_history|manual)$")
    provider: ExternalProvider | None = None
    kind: ItemKind | None = None
    query: str | None = Field(default=None, max_length=255)
    provider_item_id: str | None = Field(default=None, max_length=255)
    release_type: str | None = Field(default=None, max_length=64)
    proposal_id: UUID | None = None
    ingest_history_id: int | None = Field(default=None, ge=1)


class AdminProviderPrefillResolveResponse(BaseModel):
    source: str
    provider: ExternalProvider | None = None
    kind: ItemKind | None = None
    query: str | None = None
    provider_item_id: str | None = None
    release_type: str | None = None
    matched_rule: AdminReleaseMediaMappingRuleResponse | None = None
    notes: list[str] = Field(default_factory=list)


class AdminDeleteResponse(BaseModel):
    deleted: bool


class ProviderBatchHydrateItem(BaseModel):
    provider_item_id: str = Field(min_length=1, max_length=255)


class ProviderBatchHydrateRequest(BaseModel):
    provider: ExternalProvider
    items: list[ProviderBatchHydrateItem] = Field(min_length=1, max_length=500)


class ProviderBatchHydrateResultItem(BaseModel):
    provider_item_id: str
    success: bool
    preview: ProviderPreviewResponse | None = None
    error: str | None = None


class ProviderBatchHydrateResponse(BaseModel):
    results: list[ProviderBatchHydrateResultItem]
    total: int
    succeeded: int
    failed: int


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
    release_date: date | None = None
    imprint: str | None = Field(default=None, max_length=255)
    subtitle: str | None = Field(default=None, max_length=255)
    series_group: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=32)
    age_rating: str | None = Field(default=None, max_length=64)
    audience_rating: str | None = Field(default=None, max_length=32)
    genres: list[str] | None = None
    platforms: list[str] | None = None
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
    release_date: date | None = None
    cover_image_url: str | None = Field(default=None, max_length=1024)
    thumbnail_image_url: str | None = Field(default=None, max_length=1024)
    members: list[AdminBundleReleaseMemberUpdateRequest] | None = None


class AdminSeriesTagsUpdateRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)
    thumbnail_image_url: str | None = Field(default=None, max_length=1024)


class AdminCatalogSummaryResponse(BaseModel):
    items: int
    items_by_kind: dict[str, int] = Field(default_factory=dict)
    series: int
    volumes: int
    editions: int
    variants: int
    provider_links: int
    image_assets: int
    image_cache_entries: int
    pending_proposals: int
    missing_cover_items: int
    missing_provider_link_items: int
    duplicate_candidate_groups: int
    provider_ingest_successes: int = 0
    provider_ingest_failures: int = 0


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
    has_provider_conflicts: bool = False
    has_cover_conflicts: bool = False
    duplicate_score: int = 0
    recommended_target_item_id: UUID | None = None
    confidence_factors: list[str] = Field(default_factory=list)
    merge_warnings: list[str] = Field(default_factory=list)


class AdminDuplicateIgnoreRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=2, max_length=50)


class AdminDuplicateMergeRequest(BaseModel):
    target_item_id: UUID
    source_item_ids: list[UUID] = Field(min_length=1, max_length=49)


class AdminDuplicateActionResponse(BaseModel):
    ok: bool
    affected_items: int
    item: dict[str, Any] | None = None


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
    metadata_payload: dict[str, Any] | None = None
    status: str

    model_config = {"from_attributes": True}


class MetadataProposalAdminUpdateRequest(BaseModel):
    query: str | None = None
    provider_item_id: str | None = None
    title: str | None = None
    summary: str | None = None
    image_url: str | None = None
    metadata_payload: dict[str, Any] | None = None


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


class ProviderPayloadSnapshotPurgeResponse(BaseModel):
    purged: int
