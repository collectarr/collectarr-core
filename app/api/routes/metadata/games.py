from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import GameReleaseV1Response, GameWorkV1Response
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/games/works/{work_id}", response_model=GameWorkV1Response)
async def get_game_work(work_id: UUID, db: DbSession) -> GameWorkV1Response:
    return await MetadataService(db).get_game_work(work_id)


@router.get("/metadata/games/works/{work_id}/releases", response_model=list[GameReleaseV1Response])
async def get_game_work_releases(
    work_id: UUID,
    db: DbSession,
) -> list[GameReleaseV1Response]:
    return await MetadataService(db).get_game_work_releases(work_id)


@router.get("/metadata/games/releases/{release_id}", response_model=GameReleaseV1Response)
async def get_game_release(release_id: UUID, db: DbSession) -> GameReleaseV1Response:
    return await MetadataService(db).get_game_release(release_id)

