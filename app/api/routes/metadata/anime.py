from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import (
    AnimeEpisodeV1Response,
    AnimeReleaseEpisodeMapV1Response,
    AnimeReleaseMediaResponse,
    AnimeReleaseV1Response,
    AnimeSeriesV1Response,
)
from app.services.facade import MetadataFacade as MetadataService

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


@router.get(
    "/metadata/anime/series/{series_id}/releases",
    response_model=list[AnimeReleaseV1Response],
)
async def get_anime_series_releases(
    series_id: UUID,
    db: DbSession,
) -> list[AnimeReleaseV1Response]:
    return await MetadataService(db).get_anime_series_releases(series_id)


@router.get("/metadata/anime/episodes/{episode_id}", response_model=AnimeEpisodeV1Response)
async def get_anime_episode(episode_id: UUID, db: DbSession) -> AnimeEpisodeV1Response:
    return await MetadataService(db).get_anime_episode(episode_id)


@router.get("/metadata/anime/releases/{release_id}", response_model=AnimeReleaseV1Response)
async def get_anime_release(release_id: UUID, db: DbSession) -> AnimeReleaseV1Response:
    return await MetadataService(db).get_anime_release(release_id)


@router.get(
    "/metadata/anime/releases/{release_id}/media",
    response_model=list[AnimeReleaseMediaResponse],
)
async def get_anime_release_media(
    release_id: UUID,
    db: DbSession,
) -> list[AnimeReleaseMediaResponse]:
    return await MetadataService(db).get_anime_release_media(release_id)


@router.get(
    "/metadata/anime/releases/{release_id}/episode-map",
    response_model=list[AnimeReleaseEpisodeMapV1Response],
)
async def get_anime_release_episode_map(
    release_id: UUID,
    db: DbSession,
) -> list[AnimeReleaseEpisodeMapV1Response]:
    return await MetadataService(db).get_anime_release_episode_map(release_id)
