"""Wire schemas for source-neutral Catalog Item proposals."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.catalog.catalog_item_schema import (
    validate_catalog_item_payload,
)
from app.models.base import ItemKind
from app.types import JsonObject


class CatalogItemProposalCreate(BaseModel):
    schema_version: Literal["v1"] = "v1"
    kind: ItemKind
    catalog_item: JsonObject = Field(min_length=1)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_item(self) -> "CatalogItemProposalCreate":
        if self.kind is ItemKind.collection:
            raise ValueError("Collection is not a Catalog Item kind")
        self.catalog_item = validate_catalog_item_payload(self.kind, self.catalog_item)
        title = self.catalog_item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("catalog_item must include a non-empty title")
        if len(title.strip()) > 255:
            raise ValueError("catalog_item title must be at most 255 characters")
        return self


class CatalogItemProposalResponse(BaseModel):
    id: UUID
    schema_version: Literal["v1"] = "v1"
    kind: ItemKind
    catalog_item: JsonObject
    title: str
    status: str
    review_note: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CatalogItemProposalUpdate(BaseModel):
    catalog_item: JsonObject = Field(min_length=1)
    review_note: str | None = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}

    @field_validator("catalog_item")
    @classmethod
    def validate_catalog_item_title(cls, value: JsonObject) -> JsonObject:
        title = value.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("catalog_item must include a non-empty title")
        if len(title.strip()) > 255:
            raise ValueError("catalog_item title must be at most 255 characters")
        return value
