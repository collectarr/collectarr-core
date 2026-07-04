from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import (
    TVEpisodeV1Response,
    TVReleaseEpisodeMapV1Response,
    TVReleaseMediaResponse,
    TVReleaseV1Response,
    TVSeasonV1Response,
    TVSeriesV1Response,
)
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


@router.get("/metadata/tv/series/{series_id}/releases", response_model=list[TVReleaseV1Response])
async def get_tv_series_releases(
    series_id: UUID,
    db: DbSession,
) -> list[TVReleaseV1Response]:
    return await MetadataService(db).get_tv_series_releases(series_id)


@router.get("/metadata/tv/seasons/{season_id}", response_model=TVSeasonV1Response)
async def get_tv_season(season_id: UUID, db: DbSession) -> TVSeasonV1Response:
    return await MetadataService(db).get_tv_season(season_id)


@router.get("/metadata/tv/seasons/{season_id}/episodes", response_model=list[TVEpisodeV1Response])
async def get_tv_season_episodes(
    season_id: UUID,
    db: DbSession,
) -> list[TVEpisodeV1Response]:
    return await MetadataService(db).get_tv_season_episodes(season_id)

@router.get("/metadata/tv/episodes/{episode_id}", response_model=TVEpisodeV1Response)
async def get_tv_episode(episode_id: UUID, db: DbSession) -> TVEpisodeV1Response:
    return await MetadataService(db).get_tv_episode(episode_id)


@router.get("/metadata/tv/releases/{release_id}", response_model=TVReleaseV1Response)
async def get_tv_release(release_id: UUID, db: DbSession) -> TVReleaseV1Response:
    return await MetadataService(db).get_tv_release(release_id)


@router.get("/metadata/tv/releases/{release_id}/media", response_model=list[TVReleaseMediaResponse])
async def get_tv_release_media(
    release_id: UUID,
    db: DbSession,
) -> list[TVReleaseMediaResponse]:
    return await MetadataService(db).get_tv_release_media(release_id)


@router.get(
    "/metadata/tv/releases/{release_id}/episode-map",
    response_model=list[TVReleaseEpisodeMapV1Response],
)
async def get_tv_release_episode_map(
    release_id: UUID,
    db: DbSession,
) -> list[TVReleaseEpisodeMapV1Response]:
    return await MetadataService(db).get_tv_release_episode_map(release_id)


@router.get("/metadata/tv/media/{media_id}", response_model=TVReleaseMediaResponse)
async def get_tv_release_media_item(
    media_id: UUID,
    db: DbSession,
) -> TVReleaseMediaResponse:
    return await MetadataService(db).get_tv_release_media_item(media_id)
