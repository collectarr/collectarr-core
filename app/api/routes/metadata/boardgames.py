from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import BoardGameEditionV1Response, BoardGameWorkV1Response
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get(
    "/metadata/boardgames/works/{work_id}",
    response_model=BoardGameWorkV1Response,
)
async def get_boardgame_work(work_id: UUID, db: DbSession) -> BoardGameWorkV1Response:
    return await MetadataService(db).get_boardgame_work(work_id)


@router.get(
    "/metadata/boardgames/works/{work_id}/editions",
    response_model=list[BoardGameEditionV1Response],
)
async def get_boardgame_work_editions(
    work_id: UUID,
    db: DbSession,
) -> list[BoardGameEditionV1Response]:
    return await MetadataService(db).get_boardgame_work_editions(work_id)


@router.get(
    "/metadata/boardgames/editions/{edition_id}",
    response_model=BoardGameEditionV1Response,
)
async def get_boardgame_edition(
    edition_id: UUID,
    db: DbSession,
) -> BoardGameEditionV1Response:
    return await MetadataService(db).get_boardgame_edition(edition_id)

