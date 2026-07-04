from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import AnimeEpisodeV1Response, AnimeSeriesV1Response
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/anime/series/{series_id}", response_model=AnimeSeriesV1Response)
async def get_anime_series(series_id: UUID, db: DbSession) -> AnimeSeriesV1Response:
    return await MetadataService(db).get_anime_series(series_id)


@router.get(
    "/metadata/anime/series/{series_id}/episodes",
    response_model=list[AnimeEpisodeV1Response],
)
async def get_anime_series_episodes(
    series_id: UUID,
    db: DbSession,
) -> list[AnimeEpisodeV1Response]:
    return await MetadataService(db).get_anime_series_episodes(series_id)


@router.get("/metadata/anime/episodes/{episode_id}", response_model=AnimeEpisodeV1Response)
async def get_anime_episode(episode_id: UUID, db: DbSession) -> AnimeEpisodeV1Response:
    return await MetadataService(db).get_anime_episode(episode_id)
