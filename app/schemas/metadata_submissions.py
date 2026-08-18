"""Schemas for normalized metadata submissions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MetadataSubmissionRequest(BaseModel):
    """Normalized metadata envelope submission payload."""

    schema_version: str = Field(..., description="Envelope schema version (e.g. 'v1')")
    provider: str = Field(..., description="Provider identifier (e.g. 'tmdb', 'openlibrary')")
    provider_item_id: str = Field(..., description="Provider's native item ID")
    kind: str = Field(..., description="Target media kind (e.g. 'movie', 'tv', 'comic')")
    normalized: dict[str, Any] = Field(..., description="Normalized item metadata dictionary")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Provider provenance info")
    images: list[dict[str, Any]] = Field(default_factory=list, description="Provider image references")
    attribution: dict[str, Any] = Field(default_factory=dict, description="Attribution metadata")


class MetadataSubmissionResponse(BaseModel):
    """Result of processing a normalized metadata submission."""

    submission_id: UUID | None = None
    status: str = Field(..., description="'canonical_write' | 'proposal_created'")
    item_id: UUID | None = None
    kind: str
    created: bool = False
    item: Any = None
    message: str | None = None
