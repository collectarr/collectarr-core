from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind
from app.schemas.metadata import ItemResponse


class ProviderStatusResponse(BaseModel):
    name: str
    display_name: str
    kind: str
    status: str
    is_configured: bool
    supports_search: bool = True
    supports_ingest: bool = True
    requires_user_key: bool = False
    non_commercial_only: bool = False
    allows_redistribution: bool = False
    requires_attribution: bool = False
    license_name: str | None = None
    terms_url: str | None = None
    attribution_url: str | None = None
    rate_limit: str | None = None
    cache_policy: str | None = None
    message: str


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


class AdminMetadataCorrectionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    item_number: str | None = Field(default=None, max_length=64)
    synopsis: str | None = None
    page_count: int | None = Field(default=None, ge=0)
    publisher: str | None = Field(default=None, max_length=255)
    release_date: date | None = None
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
