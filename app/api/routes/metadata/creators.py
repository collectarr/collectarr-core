from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas import (
    CreatorCreditResponse,
    CreatorFacetResponse,
    CreatorResponse,
    FacetEntityIdsRequest,
)
from app.services.facade import MetadataFacade as MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/creators", response_model=list[CreatorResponse])
async def search_creators(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=200),
) -> list[CreatorResponse]:
    return await MetadataService(db).search_creators(q=q, limit=limit)


@router.get("/creators/{creator_id}/credits", response_model=list[CreatorCreditResponse])
async def get_creator_credits(
    creator_id: UUID,
    db: DbSession,
) -> list[CreatorCreditResponse]:
    return await MetadataService(db).get_creator_credits(creator_id)


@router.post("/creators/facets", response_model=list[CreatorFacetResponse])
async def get_creator_facets(
    db: DbSession,
    body: FacetEntityIdsRequest,
) -> list[CreatorFacetResponse]:
    return await MetadataService(db).get_creator_facets(body.entity_ids)


