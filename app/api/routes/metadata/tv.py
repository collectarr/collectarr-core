from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import TVEpisodeV1Response, TVSeasonV1Response, TVSeriesV1Response
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/tv/series/{series_id}", response_model=TVSeriesV1Response)
async def get_tv_series(series_id: UUID, db: DbSession) -> TVSeriesV1Response:
    return await MetadataService(db).get_tv_series(series_id)


@router.get("/metadata/tv/series/{series_id}/seasons", response_model=list[TVSeasonV1Response])
async def get_tv_series_seasons(
    series_id: UUID,
    db: DbSession,
) -> list[TVSeasonV1Response]:
    return await MetadataService(db).get_tv_series_seasons(series_id)


@router.get("/metadata/tv/episodes/{episode_id}", response_model=TVEpisodeV1Response)
async def get_tv_episode(episode_id: UUID, db: DbSession) -> TVEpisodeV1Response:
    return await MetadataService(db).get_tv_episode(episode_id)
