from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.base import SyncAction
from app.schemas.collection import OwnedItemResponse


class ClientChange(BaseModel):
    entity_type: str = Field(pattern="^(owned_item)$")
    entity_id: UUID | None = None
    device_id: str | None = Field(default=None, max_length=120)
    action: SyncAction
    payload: dict[str, Any] = Field(default_factory=dict)
    client_changed_at: datetime | None = None


class SyncPushRequest(BaseModel):
    device_id: str | None = Field(default=None, max_length=120)
    changes: list[ClientChange] = Field(default_factory=list)


class SyncChangeResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    device_id: str | None
    action: SyncAction
    payload: dict[str, Any] | None
    changed_at: datetime

    model_config = {"from_attributes": True}


class SyncPushResponse(BaseModel):
    accepted: int
    changes: list[SyncChangeResponse]


class SyncPullRequest(BaseModel):
    since: datetime | None = None


class SyncPullResponse(BaseModel):
    server_time: datetime
    collection: list[OwnedItemResponse]
    changes: list[SyncChangeResponse]
