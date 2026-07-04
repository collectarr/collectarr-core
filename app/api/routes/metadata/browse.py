from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas import (
    CharacterAppearanceResponse,
    CharacterFacetResponse,
    CharacterResponse,
    CreatorCreditResponse,
    CreatorFacetResponse,
    CreatorResponse,
    FacetEntityIdsRequest,
    StoryArcFacetResponse,
    StoryArcItemResponse,
    StoryArcResponse,
)
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.post("/story-arcs/facets", response_model=list[StoryArcFacetResponse])
async def get_story_arc_facets(
    db: DbSession,
    body: FacetEntityIdsRequest,
) -> list[StoryArcFacetResponse]:
    return await MetadataService(db).get_story_arc_facets(body.entity_ids)


@router.get("/story-arcs", response_model=list[StoryArcResponse])
async def search_story_arcs(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=200),
) -> list[StoryArcResponse]:
    return await MetadataService(db).search_story_arcs(q=q, limit=limit)


@router.get("/story-arcs/{story_arc_id}/items", response_model=list[StoryArcItemResponse])
async def get_story_arc_items(
    story_arc_id: UUID,
    db: DbSession,
) -> list[StoryArcItemResponse]:
    return await MetadataService(db).get_story_arc_items(story_arc_id)


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


@router.get("/characters", response_model=list[CharacterResponse])
async def search_characters(
    db: DbSession,
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=25, ge=1, le=200),
) -> list[CharacterResponse]:
    return await MetadataService(db).search_characters(q=q, limit=limit)


@router.get(
    "/characters/{character_id}/appearances", response_model=list[CharacterAppearanceResponse]
)
async def get_character_appearances(
    character_id: UUID,
    db: DbSession,
) -> list[CharacterAppearanceResponse]:
    return await MetadataService(db).get_character_appearances(character_id)


@router.post("/characters/facets", response_model=list[CharacterFacetResponse])
async def get_character_facets(
    db: DbSession,
    body: FacetEntityIdsRequest,
) -> list[CharacterFacetResponse]:
    return await MetadataService(db).get_character_facets(body.entity_ids)
