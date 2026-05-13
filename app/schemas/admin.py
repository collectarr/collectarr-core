from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider
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


class ProviderIngestResponse(BaseModel):
    item_id: UUID
    created: bool
    item: ItemResponse


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
