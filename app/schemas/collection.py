from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CollectionAddRequest(BaseModel):
    item_id: UUID
    edition_id: UUID | None = None
    variant_id: UUID | None = None
    collection_id: UUID | None = None
    condition: str | None = Field(default=None, max_length=64)
    grade: str | None = Field(default=None, max_length=64)
    personal_notes: str | None = None
    client_updated_at: datetime | None = None


class CollectionPatchRequest(BaseModel):
    edition_id: UUID | None = None
    variant_id: UUID | None = None
    condition: str | None = Field(default=None, max_length=64)
    grade: str | None = Field(default=None, max_length=64)
    personal_notes: str | None = None
    client_updated_at: datetime | None = None


class OwnedItemResponse(BaseModel):
    id: UUID
    collection_id: UUID
    item_id: UUID
    edition_id: UUID | None
    variant_id: UUID | None
    condition: str | None
    grade: str | None
    personal_notes: str | None
    updated_at: datetime
    deleted_at: datetime | None

    model_config = {"from_attributes": True}

