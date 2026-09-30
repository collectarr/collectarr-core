from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.errors import ApiHTTPException
from app.models import (
    AnimeCharacterAppearance,
    AnimeContribution,
    AnimeEpisode,
    AnimeRelease,
    AnimeReleaseEpisodeMap,
    AnimeReleaseMedia,
    AnimeSeries,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIssue,
    ComicStoryArcMembership,
    ComicVariant,
    ComicWork,
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaEdition,
    MangaSeriesMembership,
    MangaWork,
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
    AnimeEpisodeV1Response,
    AnimeReleaseEpisodeMapV1Response,
    AnimeReleaseMediaResponse,
    AnimeReleaseV1Response,
    AnimeSeriesV1Response,
    ComicIssueV1Response,
    ComicVariantV1Response,
    ComicWorkV1Response,
    MangaChapterV1Response,
    MangaEditionV1Response,
    MangaWorkV1Response,
    TVEpisodeV1Response,
    TVReleaseEpisodeMapV1Response,
    TVReleaseMediaResponse,
    TVReleaseV1Response,
    TVSeasonV1Response,
    TVSeriesV1Response,
)


async def get_comic_work(service, work_id: UUID) -> ComicWorkV1Response:
    work = await service.db.scalar(
        select(ComicWork)
        .where(ComicWork.id == work_id)
        .options(
            selectinload(ComicWork.contributions).selectinload(ComicContribution.person),
            selectinload(ComicWork.issues).selectinload(ComicIssue.contributions).selectinload(ComicContribution.person),
            selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
            selectinload(ComicWork.issues).selectinload(ComicIssue.variants),
            selectinload(ComicWork.issues).selectinload(ComicIssue.character_appearances).selectinload(
                ComicCharacterAppearance.character
            ),
            selectinload(ComicWork.missing_issue_entries),
            selectinload(ComicWork.issues).selectinload(ComicIssue.story_arc_memberships).selectinload(
                ComicStoryArcMembership.story_arc
            ),
        )
    )
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="comic_work_not_found",
            detail="Comic work not found",
        )
    return service._comic_work_response(work)


async def get_comic_work_issues(service, work_id: UUID) -> list[ComicIssueV1Response]:
    work = await service.db.scalar(select(ComicWork.id).where(ComicWork.id == work_id))
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="comic_work_not_found",
            detail="Comic work not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(ComicIssue)
                .where(ComicIssue.work_id == work_id)
                .options(
                    selectinload(ComicIssue.contributions).selectinload(ComicContribution.person),
                    selectinload(ComicIssue.identifiers),
                    selectinload(ComicIssue.variants),
                    selectinload(ComicIssue.character_appearances)
                    .selectinload(ComicCharacterAppearance.character),
                    selectinload(ComicIssue.story_arc_memberships).selectinload(ComicStoryArcMembership.story_arc),
                )
                .order_by(
                    ComicIssue.publication_date.asc().nullslast(),
                    ComicIssue.issue_number.asc().nullslast(),
                    ComicIssue.created_at.asc(),
                )
            )
        ).scalars()
    )
    return [service._comic_issue_response(row) for row in rows]


async def get_comic_issue(service, issue_id: UUID) -> ComicIssueV1Response:
    issue = await service.db.scalar(
        select(ComicIssue)
        .where(ComicIssue.id == issue_id)
        .options(
            selectinload(ComicIssue.contributions).selectinload(ComicContribution.person),
            selectinload(ComicIssue.identifiers),
            selectinload(ComicIssue.variants),
            selectinload(ComicIssue.character_appearances)
            .selectinload(ComicCharacterAppearance.character),
            selectinload(ComicIssue.story_arc_memberships).selectinload(ComicStoryArcMembership.story_arc),
        )
    )
    if issue is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="comic_issue_not_found",
            detail="Comic issue not found",
        )
    return service._comic_issue_response(issue)


async def get_comic_issue_variants(service, issue_id: UUID) -> list[ComicVariantV1Response]:
    issue = await service.db.scalar(select(ComicIssue.id).where(ComicIssue.id == issue_id))
    if issue is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="comic_issue_not_found",
            detail="Comic issue not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(ComicVariant)
                .where(ComicVariant.issue_id == issue_id)
                .order_by(
                    ComicVariant.release_date.asc().nullslast(),
                    ComicVariant.variant_name.asc().nullslast(),
                    ComicVariant.created_at.asc(),
                )
            )
        ).scalars()
    )
    return [service._comic_variant_response(row) for row in rows]


async def get_comic_variant(service, variant_id: UUID) -> ComicVariantV1Response:
    variant = await service.db.scalar(
        select(ComicVariant).where(ComicVariant.id == variant_id)
    )
    if variant is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="comic_variant_not_found",
            detail="Comic variant not found",
        )
    return service._comic_variant_response(variant)


async def get_manga_work(service, work_id: UUID) -> MangaWorkV1Response:
    work = await service.db.scalar(
        select(MangaWork)
        .where(MangaWork.id == work_id)
        .options(
            selectinload(MangaWork.contributions).selectinload(MangaContribution.person),
            selectinload(MangaWork.chapters),
            selectinload(MangaWork.editions),
            selectinload(MangaWork.identifiers),
            selectinload(MangaWork.character_appearances).selectinload(MangaCharacterAppearance.character),
            selectinload(MangaWork.series_memberships).selectinload(MangaSeriesMembership.series),
        )
    )
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="manga_work_not_found",
            detail="Manga work not found",
        )
    return service._manga_work_response(work)


async def get_manga_work_editions(service, work_id: UUID) -> list[MangaEditionV1Response]:
    work = await service.db.scalar(select(MangaWork.id).where(MangaWork.id == work_id))
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="manga_work_not_found",
            detail="Manga work not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(MangaEdition)
                .where(MangaEdition.work_id == work_id)
                .order_by(MangaEdition.publication_date.asc().nullslast(), MangaEdition.created_at.asc())
            )
        ).scalars()
    )
    return [service._manga_edition_response(row) for row in rows]


async def get_manga_edition(service, edition_id: UUID) -> MangaEditionV1Response:
    edition = await service.db.scalar(
        select(MangaEdition).where(MangaEdition.id == edition_id)
    )
    if edition is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="manga_edition_not_found",
            detail="Manga edition not found",
        )
    return service._manga_edition_response(edition)


async def get_manga_work_chapters(service, work_id: UUID) -> list[MangaChapterV1Response]:
    work = await service.db.scalar(select(MangaWork.id).where(MangaWork.id == work_id))
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="manga_work_not_found",
            detail="Manga work not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(MangaChapter)
                .where(MangaChapter.work_id == work_id)
                .order_by(MangaChapter.chapter_number.asc().nullslast(), MangaChapter.created_at.asc())
            )
        ).scalars()
    )
    return [service._manga_chapter_response(chapter) for chapter in rows]


async def get_manga_chapter(service, chapter_id: UUID) -> MangaChapterV1Response:
    chapter = await service.db.scalar(select(MangaChapter).where(MangaChapter.id == chapter_id))
    if chapter is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="manga_chapter_not_found",
            detail="Manga chapter not found",
        )
    return service._manga_chapter_response(chapter)


async def get_anime_series(service, series_id: UUID) -> AnimeSeriesV1Response:
    series = await service.db.scalar(
        select(AnimeSeries)
        .where(AnimeSeries.id == series_id)
        .options(
            selectinload(AnimeSeries.contributions).selectinload(AnimeContribution.person),
            selectinload(AnimeSeries.episodes),
            selectinload(AnimeSeries.releases).selectinload(AnimeRelease.media),
            selectinload(AnimeSeries.releases).selectinload(AnimeRelease.episode_mappings),
            selectinload(AnimeSeries.identifiers),
            selectinload(AnimeSeries.character_appearances).selectinload(AnimeCharacterAppearance.character),
        )
    )
    if series is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="anime_series_not_found",
            detail="Anime series not found",
        )
    return service._anime_series_response(series)


async def get_anime_series_releases(service, series_id: UUID) -> list[AnimeReleaseV1Response]:
    series = await service.db.scalar(select(AnimeSeries.id).where(AnimeSeries.id == series_id))
    if series is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="anime_series_not_found",
            detail="Anime work not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(AnimeRelease)
                .where(AnimeRelease.work_id == series_id)
                .options(
                    selectinload(AnimeRelease.media),
                    selectinload(AnimeRelease.episode_mappings),
                )
                .order_by(AnimeRelease.release_date.asc().nullslast(), AnimeRelease.created_at.asc())
            )
        ).scalars()
    )
    return [service._anime_release_response(row) for row in rows]


async def get_anime_release(service, release_id: UUID) -> AnimeReleaseV1Response:
    release = await service.db.scalar(
        select(AnimeRelease)
        .where(AnimeRelease.id == release_id)
        .options(
            selectinload(AnimeRelease.media),
            selectinload(AnimeRelease.episode_mappings),
        )
    )
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="anime_release_not_found",
            detail="Anime release not found",
        )
    return service._anime_release_response(release)


async def get_anime_release_media(service, release_id: UUID) -> list[AnimeReleaseMediaResponse]:
    release = await service.db.scalar(select(AnimeRelease.id).where(AnimeRelease.id == release_id))
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="anime_release_not_found",
            detail="Anime release not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(AnimeReleaseMedia)
                .where(AnimeReleaseMedia.release_id == release_id)
                .order_by(AnimeReleaseMedia.media_number.asc(), AnimeReleaseMedia.created_at.asc())
            )
        ).scalars()
    )
    return [service._anime_release_media_response(row) for row in rows]


async def get_anime_release_episode_map(
    service,
    release_id: UUID,
) -> list[AnimeReleaseEpisodeMapV1Response]:
    release = await service.db.scalar(select(AnimeRelease.id).where(AnimeRelease.id == release_id))
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="anime_release_not_found",
            detail="Anime release not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(AnimeReleaseEpisodeMap)
                .where(AnimeReleaseEpisodeMap.release_id == release_id)
                .order_by(
                    AnimeReleaseEpisodeMap.disc_number.asc().nullslast(),
                    AnimeReleaseEpisodeMap.sequence_number.asc().nullslast(),
                    AnimeReleaseEpisodeMap.created_at.asc(),
                )
            )
        ).scalars()
    )
    return [service._anime_release_episode_map_response(row) for row in rows]


async def get_anime_series_episodes(service, series_id: UUID) -> list[AnimeEpisodeV1Response]:
    series = await service.db.scalar(select(AnimeSeries.id).where(AnimeSeries.id == series_id))
    if series is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="anime_series_not_found",
            detail="Anime series not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(AnimeEpisode)
                .where(AnimeEpisode.series_id == series_id)
                .order_by(AnimeEpisode.episode_number.asc().nullslast(), AnimeEpisode.created_at.asc())
            )
        ).scalars()
    )
    return [service._anime_episode_response(episode) for episode in rows]


async def get_anime_episode(service, episode_id: UUID) -> AnimeEpisodeV1Response:
    episode = await service.db.scalar(select(AnimeEpisode).where(AnimeEpisode.id == episode_id))
    if episode is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="anime_episode_not_found",
            detail="Anime episode not found",
        )
    return service._anime_episode_response(episode)


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
