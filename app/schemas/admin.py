from uuid import UUID
from datetime import datetime

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
