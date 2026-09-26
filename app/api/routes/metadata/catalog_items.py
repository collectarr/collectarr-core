from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.catalog_item_v1 import CatalogItemSummaryV1, CatalogItemV1, CatalogItemWriteV1
from app.services.catalog_item_service import CatalogItemService

CatalogItemKind = Literal[
    "anime", "boardgame", "book", "comic", "game", "manga", "movie", "music", "tv"
]

router = APIRouter(tags=["catalog-items"])


@router.get("/metadata/catalog/items", response_model=list[CatalogItemSummaryV1])
async def search_catalog_items(
    db: DbSession,
    kind: CatalogItemKind | None = None,
    q: str | None = None,
    identifier: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CatalogItemSummaryV1]:
    return await CatalogItemService(db).search_items(
        kind=kind,
        query=q,
        identifier=identifier,
        limit=limit,
    )


@router.get("/metadata/catalog/items/{item_id}", response_model=CatalogItemV1)
async def get_catalog_item(item_id: UUID, db: DbSession) -> CatalogItemV1:
    return await CatalogItemService(db).get_item(item_id)


@router.post(
    "/metadata/catalog/items",
    response_model=CatalogItemV1,
    status_code=201,
)
async def create_catalog_item(
    payload: CatalogItemWriteV1,
    db: DbSession,
    _user: CurrentAdmin,
) -> CatalogItemV1:
    return await CatalogItemService(db).create_item(payload)


@router.put("/metadata/catalog/items/{item_id}", response_model=CatalogItemV1)
async def update_catalog_item(
    item_id: UUID,
    payload: CatalogItemWriteV1,
    db: DbSession,
    _user: CurrentAdmin,
) -> CatalogItemV1:
    return await CatalogItemService(db).update_item(item_id, payload)
