"""Shared response envelope for flattened Catalog Item schemas."""

from uuid import UUID

from pydantic import BaseModel


class CatalogItemBaseResponse(BaseModel):
    id: UUID
    kind: str
    title: str
    revision: int
