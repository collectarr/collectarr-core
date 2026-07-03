from __future__ import annotations

from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.errors import ApiHTTPException
from app.models import (
    AnimeCharacterAppearance,
    AnimeContribution,
    AnimeEpisode,
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookSeriesMembership,
    BookWork,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIssue,
    ComicStoryArcMembership,
    ComicWork,
    GameRelease,
    GameWork,
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaSeriesMembership,
    MangaWork,
    MovieRelease,
    MovieWork,
    MovieWorkContribution,
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicTrack,
    TVEpisode,
    TVRelease,
    TVReleaseContribution,
)
from app.schemas import (
    AnimeEpisodeV1Response,
    AnimeSeriesV1Response,
    BoardGameEditionV1Response,
    BoardGameWorkV1Response,
    BookEditionV1Response,
    BookWorkV1Response,
    ComicIssueV1Response,
    ComicWorkV1Response,
    GameReleaseV1Response,
    GameWorkV1Response,
    MangaChapterV1Response,
    MangaWorkV1Response,
    MovieReleaseV1Response,
    MovieWorkV1Response,
    MusicMediaV1Response,
    MusicReleaseV1Response,
    MusicTrackV1Response,
    TVEpisodeV1Response,
    TVSeasonV1Response,
    TVSeriesV1Response,
)


async def get_book_work(service, work_id: UUID) -> BookWorkV1Response:
    work = await service.db.scalar(
        select(BookWork)
        .where(BookWork.id == work_id)
        .options(
            selectinload(BookWork.contributions).selectinload(BookContribution.person),
            selectinload(BookWork.series_memberships).selectinload(BookSeriesMembership.series),
            selectinload(BookWork.editions).selectinload(BookEdition.contributions).selectinload(BookContribution.person),
            selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
        )
    )
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="book_work_not_found",
            detail="Book work not found",
        )
    return service._book_work_response(work)


async def get_book_work_editions(service, work_id: UUID) -> list[BookEditionV1Response]:
    work = await service.db.scalar(select(BookWork.id).where(BookWork.id == work_id))
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="book_work_not_found",
            detail="Book work not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(BookEdition)
                .where(BookEdition.work_id == work_id)
                .options(
                    selectinload(BookEdition.contributions).selectinload(BookContribution.person),
                    selectinload(BookEdition.identifiers),
                )
                .order_by(BookEdition.publication_date.asc().nullslast(), BookEdition.created_at.asc())
            )
        ).scalars()
    )
    return [service._book_edition_response(row) for row in rows]


async def get_book_edition(service, edition_id: UUID) -> BookEditionV1Response:
    edition = await service.db.scalar(
        select(BookEdition)
        .where(BookEdition.id == edition_id)
        .options(
            selectinload(BookEdition.contributions).selectinload(BookContribution.person),
            selectinload(BookEdition.identifiers),
        )
    )
    if edition is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="book_edition_not_found",
            detail="Book edition not found",
        )
    return service._book_edition_response(edition)


async def get_game_work(service, work_id: UUID) -> GameWorkV1Response:
    work = await service.db.scalar(
        select(GameWork).where(GameWork.id == work_id).options(selectinload(GameWork.releases))
    )
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="game_work_not_found",
            detail="Game work not found",
        )
    return service._game_work_response(work)


async def get_game_work_releases(service, work_id: UUID) -> list[GameReleaseV1Response]:
    work = await service.db.scalar(select(GameWork.id).where(GameWork.id == work_id))
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="game_work_not_found",
            detail="Game work not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(GameRelease)
                .where(GameRelease.work_id == work_id)
                .order_by(GameRelease.release_date.asc().nullslast(), GameRelease.created_at.asc())
            )
        ).scalars()
    )
    return [service._game_release_response(row) for row in rows]


async def get_game_release(service, release_id: UUID) -> GameReleaseV1Response:
    release = await service.db.scalar(select(GameRelease).where(GameRelease.id == release_id))
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="game_release_not_found",
            detail="Game release not found",
        )
    return service._game_release_response(release)


async def get_boardgame_work(service, work_id: UUID) -> BoardGameWorkV1Response:
    work = await service.db.scalar(
        select(BoardGameWork).where(BoardGameWork.id == work_id).options(selectinload(BoardGameWork.editions))
    )
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="boardgame_work_not_found",
            detail="Board game work not found",
        )
    return service._boardgame_work_response(work)


async def get_boardgame_work_editions(service, work_id: UUID) -> list[BoardGameEditionV1Response]:
    work = await service.db.scalar(select(BoardGameWork.id).where(BoardGameWork.id == work_id))
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="boardgame_work_not_found",
            detail="Board game work not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(BoardGameEdition)
                .where(BoardGameEdition.work_id == work_id)
                .order_by(BoardGameEdition.release_date.asc().nullslast(), BoardGameEdition.created_at.asc())
            )
        ).scalars()
    )
    return [service._boardgame_edition_response(row) for row in rows]


async def get_boardgame_edition(service, edition_id: UUID) -> BoardGameEditionV1Response:
    edition = await service.db.scalar(select(BoardGameEdition).where(BoardGameEdition.id == edition_id))
    if edition is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="boardgame_edition_not_found",
            detail="Board game edition not found",
        )
    return service._boardgame_edition_response(edition)


async def get_comic_work(service, work_id: UUID) -> ComicWorkV1Response:
    work = await service.db.scalar(
        select(ComicWork)
        .where(ComicWork.id == work_id)
        .options(
            selectinload(ComicWork.contributions).selectinload(ComicContribution.person),
            selectinload(ComicWork.issues).selectinload(ComicIssue.contributions).selectinload(ComicContribution.person),
            selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
            selectinload(ComicWork.issues).selectinload(ComicIssue.character_appearances).selectinload(
                ComicCharacterAppearance.character
            ),
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
                    selectinload(ComicIssue.character_appearances).selectinload(ComicCharacterAppearance.character),
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
            selectinload(ComicIssue.character_appearances).selectinload(ComicCharacterAppearance.character),
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


async def get_manga_work(service, work_id: UUID) -> MangaWorkV1Response:
    work = await service.db.scalar(
        select(MangaWork)
        .where(MangaWork.id == work_id)
        .options(
            selectinload(MangaWork.contributions).selectinload(MangaContribution.person),
            selectinload(MangaWork.chapters),
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


async def get_movie_work(service, work_id: UUID) -> MovieWorkV1Response:
    work = await service.db.scalar(
        select(MovieWork)
        .where(MovieWork.id == work_id)
        .options(
            selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
            selectinload(MovieWork.releases).selectinload(MovieRelease.media),
            selectinload(MovieWork.identifiers),
        )
    )
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="movie_work_not_found",
            detail="Movie work not found",
        )
    return service._movie_work_response(work)


async def get_movie_work_releases(service, work_id: UUID) -> list[MovieReleaseV1Response]:
    work = await service.db.scalar(select(MovieWork.id).where(MovieWork.id == work_id))
    if work is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="movie_work_not_found",
            detail="Movie work not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(MovieRelease)
                .where(MovieRelease.work_id == work_id)
                .options(selectinload(MovieRelease.media))
                .order_by(MovieRelease.release_date.asc().nullslast(), MovieRelease.created_at.asc())
            )
        ).scalars()
    )
    return [service._movie_release_response(release) for release in rows]


async def get_movie_release(service, release_id: UUID) -> MovieReleaseV1Response:
    release = await service.db.scalar(
        select(MovieRelease).where(MovieRelease.id == release_id).options(selectinload(MovieRelease.media))
    )
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="movie_release_not_found",
            detail="Movie release not found",
        )
    return service._movie_release_response(release)


async def get_music_release(service, release_id: UUID) -> MusicReleaseV1Response:
    release = await service.db.scalar(
        select(MusicRelease)
        .where(MusicRelease.id == release_id)
        .options(
            selectinload(MusicRelease.contributions).selectinload(MusicReleaseContribution.person),
            selectinload(MusicRelease.media).selectinload(MusicMedia.tracks),
            selectinload(MusicRelease.identifiers),
        )
    )
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="music_release_not_found",
            detail="Music release not found",
        )
    return service._music_release_response(release)


async def get_music_release_media(service, release_id: UUID) -> list[MusicMediaV1Response]:
    release = await service.db.scalar(select(MusicRelease.id).where(MusicRelease.id == release_id))
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="music_release_not_found",
            detail="Music release not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(MusicMedia)
                .where(MusicMedia.release_id == release_id)
                .options(selectinload(MusicMedia.tracks))
                .order_by(MusicMedia.media_number.asc(), MusicMedia.created_at.asc())
            )
        ).scalars()
    )
    return [service._music_media_response(media) for media in rows]


async def get_music_media(service, media_id: UUID) -> MusicMediaV1Response:
    media = await service.db.scalar(select(MusicMedia).where(MusicMedia.id == media_id).options(selectinload(MusicMedia.tracks)))
    if media is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="music_media_not_found",
            detail="Music media not found",
        )
    return service._music_media_response(media)


async def get_music_media_tracks(service, media_id: UUID) -> list[MusicTrackV1Response]:
    media = await service.db.scalar(select(MusicMedia.id).where(MusicMedia.id == media_id))
    if media is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="music_media_not_found",
            detail="Music media not found",
        )
    rows = list(
        (
            await service.db.execute(
                select(MusicTrack)
                .where(MusicTrack.media_id == media_id)
                .order_by(MusicTrack.position.asc(), MusicTrack.created_at.asc())
            )
        ).scalars()
    )
    return [service._music_track_response(track) for track in rows]


async def get_music_track(service, track_id: UUID) -> MusicTrackV1Response:
    track = await service.db.scalar(select(MusicTrack).where(MusicTrack.id == track_id))
    if track is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="music_track_not_found",
            detail="Music track not found",
        )
    return service._music_track_response(track)


async def get_tv_series(service, series_id: UUID) -> TVSeriesV1Response:
    release = await service.db.scalar(
        select(TVRelease)
        .where(TVRelease.id == series_id)
        .options(
            selectinload(TVRelease.contributions).selectinload(TVReleaseContribution.person),
            selectinload(TVRelease.episodes),
            selectinload(TVRelease.media),
            selectinload(TVRelease.identifiers),
        )
    )
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_release_not_found",
            detail="TV release not found",
        )
    return service._tv_series_response(release)


async def get_tv_series_seasons(service, series_id: UUID) -> list[TVSeasonV1Response]:
    release = await service.db.scalar(
        select(TVRelease)
        .where(TVRelease.id == series_id)
        .options(
            selectinload(TVRelease.contributions).selectinload(TVReleaseContribution.person),
            selectinload(TVRelease.episodes),
            selectinload(TVRelease.media),
            selectinload(TVRelease.identifiers),
        )
    )
    if release is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_release_not_found",
            detail="TV release not found",
        )
    return service._tv_series_response(release).seasons


async def get_tv_episode(service, episode_id: UUID) -> TVEpisodeV1Response:
    episode = await service.db.scalar(select(TVEpisode).where(TVEpisode.id == episode_id))
    if episode is None:
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="tv_episode_not_found",
            detail="TV episode not found",
        )
    return service._tv_episode_response(episode)
