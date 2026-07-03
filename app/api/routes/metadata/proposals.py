from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import (
    CharacterFacetResponse,
    CreatorFacetResponse,
    FacetItemIdsRequest,
    MetadataProposalCreate,
    MetadataProposalResponse,
    StoryArcFacetResponse,
)
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.post("/metadata/proposals", response_model=MetadataProposalResponse, status_code=201)
async def create_metadata_proposal(
    payload: MetadataProposalCreate,
    db: DbSession,
) -> MetadataProposalResponse:
    return await MetadataService(db).create_proposal(payload)


@router.post("/story-arcs/facets", response_model=list[StoryArcFacetResponse])
async def get_story_arc_facets(
    db: DbSession,
    body: FacetItemIdsRequest,
) -> list[StoryArcFacetResponse]:
    return await MetadataService(db).get_story_arc_facets(body.item_ids)


@router.post("/characters/facets", response_model=list[CharacterFacetResponse])
async def get_character_facets(
    db: DbSession,
    body: FacetItemIdsRequest,
) -> list[CharacterFacetResponse]:
    return await MetadataService(db).get_character_facets(body.item_ids)


@router.post("/creators/facets", response_model=list[CreatorFacetResponse])
async def get_creator_facets(
    db: DbSession,
    body: FacetItemIdsRequest,
) -> list[CreatorFacetResponse]:
    return await MetadataService(db).get_creator_facets(body.item_ids)

