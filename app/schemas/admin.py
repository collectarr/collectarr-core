from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider
from app.schemas.metadata import ItemResponse


class ProviderStatusResponse(BaseModel):
    name: str
    kind: str
    status: str
    is_configured: bool
    supports_search: bool = True
    supports_ingest: bool = True
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
