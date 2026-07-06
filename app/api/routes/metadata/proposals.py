from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import (
    CharacterFacetResponse,
    CreatorFacetResponse,
    FacetEntityIdsRequest,
    MetadataProposalCreate,
    MetadataProposalResponse,
    StoryArcFacetResponse,
)
from app.services.facade import MetadataFacade as MetadataService

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
    body: FacetEntityIdsRequest,
) -> list[StoryArcFacetResponse]:
    return await MetadataService(db).get_story_arc_facets(body.entity_ids)


@router.post("/characters/facets", response_model=list[CharacterFacetResponse])
async def get_character_facets(
    db: DbSession,
    body: FacetEntityIdsRequest,
) -> list[CharacterFacetResponse]:
    return await MetadataService(db).get_character_facets(body.entity_ids)


@router.post("/creators/facets", response_model=list[CreatorFacetResponse])
async def get_creator_facets(
    db: DbSession,
    body: FacetEntityIdsRequest,
) -> list[CreatorFacetResponse]:
    return await MetadataService(db).get_creator_facets(body.entity_ids)
