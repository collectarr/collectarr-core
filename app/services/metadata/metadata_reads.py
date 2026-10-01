from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.errors import ApiHTTPException
from app.models import (
    TVEpisode,
    TVEpisodeContribution,
    TVRelease,
    TVReleaseContribution,
    TVReleaseEpisodeMap,
    TVReleaseMedia,
    TVSeason,
    TVSeries,
)
from app.schemas import (
    TVEpisodeV1Response,
    TVReleaseEpisodeMapV1Response,
    TVReleaseMediaResponse,
    TVReleaseV1Response,
    TVSeasonV1Response,
    TVSeriesV1Response,
)


async def get_tv_series(service, series_id: UUID) -> TVSeriesV1Response:
    series = await service.db.scalar(
        select(TVSeries)
        .where(TVSeries.id == series_id)
        .options(
            selectinload(TVSeries.seasons).selectinload(TVSeason.episodes),
            selectinload(TVSeries.releases).selectinload(TVRelease.media),
            selectinload(TVSeries.releases).selectinload(TVRelease.episode_mappings),
            selectinload(TVSeries.releases).selectinload(TVRelease.contributions).selectinload(
                TVReleaseContribution.person
            ),
            selectinload(TVSeries.releases).selectinload(TVRelease.identifiers),
        )
    )
    if series is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_series_not_found",
            detail="TV series not found",
        )
    return service._tv_series_response(series)


async def get_tv_series_releases(service, series_id: UUID) -> list[TVReleaseV1Response]:
    series = await service.db.scalar(select(TVSeries.id).where(TVSeries.id == series_id))
    if series is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_series_not_found",
            detail="TV series not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(TVRelease)
                .where(TVRelease.series_id == series_id)
                .options(
                    selectinload(TVRelease.media),
                    selectinload(TVRelease.episode_mappings),
                    selectinload(TVRelease.contributions).selectinload(TVReleaseContribution.person),
                    selectinload(TVRelease.identifiers),
                )
                .order_by(TVRelease.release_date.asc().nullslast(), TVRelease.created_at.asc())
            )
        ).scalars()
    )
    return [service._tv_release_response(row) for row in rows]


async def get_tv_season(service, season_id: UUID) -> TVSeasonV1Response:
    season = await service.db.scalar(
        select(TVSeason)
        .where(TVSeason.id == season_id)
        .options(selectinload(TVSeason.episodes))
    )
    if season is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_season_not_found",
            detail="TV season not found",
        )
    return service._tv_season_response(season)


async def get_tv_season_episodes(service, season_id: UUID) -> list[TVEpisodeV1Response]:
    season = await service.db.scalar(
        select(TVSeason)
        .where(TVSeason.id == season_id)
        .options(selectinload(TVSeason.episodes))
    )
    if season is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_season_not_found",
            detail="TV season not found",
        )
    return [service._tv_episode_response(episode) for episode in sorted(
        season.episodes or [],
        key=lambda episode: (episode.episode_number, episode.original_air_date or date.max, str(episode.id)),
    )]


async def get_tv_release(service, release_id: UUID) -> TVReleaseV1Response:
    release = await service.db.scalar(
        select(TVRelease)
        .where(TVRelease.id == release_id)
        .options(
            selectinload(TVRelease.media),
            selectinload(TVRelease.episode_mappings),
            selectinload(TVRelease.contributions).selectinload(TVReleaseContribution.person),
            selectinload(TVRelease.identifiers),
        )
    )
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_release_not_found",
            detail="TV release not found",
        )
    return service._tv_release_response(release)


async def get_tv_release_media(service, release_id: UUID) -> list[TVReleaseMediaResponse]:
    release = await service.db.scalar(select(TVRelease.id).where(TVRelease.id == release_id))
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_release_not_found",
            detail="TV release not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(TVReleaseMedia)
                .where(TVReleaseMedia.release_id == release_id)
                .order_by(TVReleaseMedia.media_number.asc(), TVReleaseMedia.created_at.asc())
            )
        ).scalars()
    )
    return [service._tv_release_media_response(row) for row in rows]


async def get_tv_release_episode_map(
    service,
    release_id: UUID,
) -> list[TVReleaseEpisodeMapV1Response]:
    release = await service.db.scalar(select(TVRelease.id).where(TVRelease.id == release_id))
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_release_not_found",
            detail="TV release not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(TVReleaseEpisodeMap)
                .where(TVReleaseEpisodeMap.release_id == release_id)
                .order_by(
                    TVReleaseEpisodeMap.disc_number.asc().nullslast(),
                    TVReleaseEpisodeMap.sequence_number.asc().nullslast(),
                    TVReleaseEpisodeMap.created_at.asc(),
                )
            )
        ).scalars()
    )
    return [service._tv_release_episode_map_response(row) for row in rows]


async def get_tv_release_media_item(service, media_id: UUID) -> TVReleaseMediaResponse:
    media = await service.db.scalar(select(TVReleaseMedia).where(TVReleaseMedia.id == media_id))
    if media is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_release_media_not_found",
            detail="TV release media not found",
        )
    return service._tv_release_media_response(media)


async def get_tv_series_seasons(service, series_id: UUID) -> list[TVSeasonV1Response]:
    series = await service.db.scalar(
        select(TVSeries)
        .where(TVSeries.id == series_id)
        .options(selectinload(TVSeries.seasons).selectinload(TVSeason.episodes))
    )
    if series is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_series_not_found",
            detail="TV series not found",
        )
    return [
        service._tv_season_response(season)
        for season in sorted(series.seasons or [], key=lambda row: (row.season_number, str(row.id)))
    ]


async def get_tv_episode(service, episode_id: UUID) -> TVEpisodeV1Response:
    episode = await service.db.scalar(
        select(TVEpisode)
        .where(TVEpisode.id == episode_id)
        .options(
            selectinload(TVEpisode.season),
            selectinload(TVEpisode.release),
            selectinload(TVEpisode.media),
            selectinload(TVEpisode.identifiers),
            selectinload(TVEpisode.contributions).selectinload(TVEpisodeContribution.person),
        )
    )
    if episode is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_episode_not_found",
            detail="TV episode not found",
        )
    return service._tv_episode_response(episode)
