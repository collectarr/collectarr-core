from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.base import ItemKind
from app.types import JsonObject


class CanonicalCorrectionProposalCreate(BaseModel):
    """A provider-independent proposal against one canonical entity."""

    kind: ItemKind
    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: UUID
    scope: str = Field(min_length=1, max_length=64)
    base_revision: str | None = Field(default=None, min_length=1, max_length=128)
    base_hash: str | None = Field(default=None, min_length=1, max_length=128)
    proposed_fields: JsonObject = Field(min_length=1)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def require_base_and_fields(self) -> "CanonicalCorrectionProposalCreate":
        if self.base_revision is None and self.base_hash is None:
            raise ValueError("base_revision or base_hash is required")
        if not self.proposed_fields:
            raise ValueError("proposed_fields must not be empty")
        return self


class CanonicalCorrectionProposalResponse(BaseModel):
    id: UUID
    kind: ItemKind
    entity_type: str
    entity_id: UUID
    scope: str
    base_revision: str | None
    base_hash: str | None
    proposed_fields: JsonObject
    status: str
