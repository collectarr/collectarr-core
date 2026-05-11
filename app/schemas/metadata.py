from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import ExternalProvider, ItemKind


class VariantResponse(BaseModel):
    id: UUID
    name: str
    sku: str | None
    cover_image_url: str | None
    thumbnail_image_url: str | None
    is_primary: bool

    model_config = {"from_attributes": True}


class EditionResponse(BaseModel):
    id: UUID
    title: str
    format: str | None
    publisher: str | None
    isbn: str | None
    upc: str | None
    language: str | None
    release_date: date | None
    variants: list[VariantResponse] = []

    model_config = {"from_attributes": True}


class ItemResponse(BaseModel):
    id: UUID
    kind: ItemKind
    title: str
    item_number: str | None
    sort_key: str | None
    synopsis: str | None
    editions: list[EditionResponse] = []

    model_config = {"from_attributes": True}


class SearchResult(BaseModel):
    id: UUID
    kind: ItemKind
    title: str
    item_number: str | None = None
    synopsis: str | None = None
    cover_image_url: str | None = None
    thumbnail_image_url: str | None = None


class ProviderSearchResultResponse(BaseModel):
    provider: ExternalProvider
    provider_item_id: str
    title: str
    kind: ItemKind
    summary: str | None = None
    image_url: str | None = None


class MetadataProposalCreate(BaseModel):
    provider: ExternalProvider = ExternalProvider.comicvine
    provider_item_id: str | None = Field(default=None, max_length=255)
    query: str = Field(min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    image_url: str | None = Field(default=None, max_length=1024)


class MetadataProposalResponse(BaseModel):
    id: UUID
    provider: ExternalProvider
    provider_item_id: str | None
    query: str
    title: str | None
    status: str

    model_config = {"from_attributes": True}
