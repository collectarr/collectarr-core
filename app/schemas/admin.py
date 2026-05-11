from uuid import UUID

from pydantic import BaseModel, Field

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
    provider: str = Field(pattern="^(comicvine|igdb|tmdb)$")
    provider_item_id: str = Field(min_length=1, max_length=255)


class ProviderSearchRequest(BaseModel):
    provider: str = Field(pattern="^(comicvine|igdb|tmdb)$")
    query: str = Field(min_length=1, max_length=255)


class ProviderIngestResponse(BaseModel):
    item_id: UUID
    created: bool
    item: ItemResponse
