from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
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
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/books/works/{work_id}", response_model=BookWorkV1Response)
async def get_book_work(work_id: UUID, db: DbSession) -> BookWorkV1Response:
    return await MetadataService(db).get_book_work(work_id)


@router.get("/metadata/books/works/{work_id}/editions", response_model=list[BookEditionV1Response])
async def get_book_work_editions(
    work_id: UUID,
    db: DbSession,
) -> list[BookEditionV1Response]:
    return await MetadataService(db).get_book_work_editions(work_id)


@router.get("/metadata/books/editions/{edition_id}", response_model=BookEditionV1Response)
async def get_book_edition(edition_id: UUID, db: DbSession) -> BookEditionV1Response:
    return await MetadataService(db).get_book_edition(edition_id)


@router.get("/metadata/comics/works/{work_id}", response_model=ComicWorkV1Response)
async def get_comic_work(work_id: UUID, db: DbSession) -> ComicWorkV1Response:
    return await MetadataService(db).get_comic_work(work_id)


@router.get("/metadata/comics/works/{work_id}/issues", response_model=list[ComicIssueV1Response])
async def get_comic_work_issues(
    work_id: UUID,
    db: DbSession,
) -> list[ComicIssueV1Response]:
    return await MetadataService(db).get_comic_work_issues(work_id)


@router.get("/metadata/comics/issues/{issue_id}", response_model=ComicIssueV1Response)
async def get_comic_issue(issue_id: UUID, db: DbSession) -> ComicIssueV1Response:
    return await MetadataService(db).get_comic_issue(issue_id)


@router.get("/metadata/manga/works/{work_id}", response_model=MangaWorkV1Response)
async def get_manga_work(work_id: UUID, db: DbSession) -> MangaWorkV1Response:
    return await MetadataService(db).get_manga_work(work_id)


@router.get("/metadata/manga/works/{work_id}/chapters", response_model=list[MangaChapterV1Response])
async def get_manga_work_chapters(
    work_id: UUID,
    db: DbSession,
) -> list[MangaChapterV1Response]:
    return await MetadataService(db).get_manga_work_chapters(work_id)


@router.get("/metadata/manga/chapters/{chapter_id}", response_model=MangaChapterV1Response)
async def get_manga_chapter(chapter_id: UUID, db: DbSession) -> MangaChapterV1Response:
    return await MetadataService(db).get_manga_chapter(chapter_id)


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


@router.get("/metadata/movies/works/{work_id}", response_model=MovieWorkV1Response)
async def get_movie_work(work_id: UUID, db: DbSession) -> MovieWorkV1Response:
    return await MetadataService(db).get_movie_work(work_id)


@router.get(
    "/metadata/movies/works/{work_id}/releases",
    response_model=list[MovieReleaseV1Response],
)
async def get_movie_work_releases(
    work_id: UUID,
    db: DbSession,
) -> list[MovieReleaseV1Response]:
    return await MetadataService(db).get_movie_work_releases(work_id)


@router.get("/metadata/movies/releases/{release_id}", response_model=MovieReleaseV1Response)
async def get_movie_release(release_id: UUID, db: DbSession) -> MovieReleaseV1Response:
    return await MetadataService(db).get_movie_release(release_id)


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


@router.get("/metadata/boardgames/works/{work_id}", response_model=BoardGameWorkV1Response)
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


@router.get("/metadata/boardgames/editions/{edition_id}", response_model=BoardGameEditionV1Response)
async def get_boardgame_edition(
    edition_id: UUID,
    db: DbSession,
) -> BoardGameEditionV1Response:
    return await MetadataService(db).get_boardgame_edition(edition_id)


@router.get("/metadata/music/releases/{release_id}", response_model=MusicReleaseV1Response)
async def get_music_release(release_id: UUID, db: DbSession) -> MusicReleaseV1Response:
    return await MetadataService(db).get_music_release(release_id)


@router.get("/metadata/music/releases/{release_id}/media", response_model=list[MusicMediaV1Response])
async def get_music_release_media(
    release_id: UUID,
    db: DbSession,
) -> list[MusicMediaV1Response]:
    return await MetadataService(db).get_music_release_media(release_id)


@router.get("/metadata/music/media/{media_id}", response_model=MusicMediaV1Response)
async def get_music_media(media_id: UUID, db: DbSession) -> MusicMediaV1Response:
    return await MetadataService(db).get_music_media(media_id)


@router.get("/metadata/music/media/{media_id}/tracks", response_model=list[MusicTrackV1Response])
async def get_music_media_tracks(
    media_id: UUID,
    db: DbSession,
) -> list[MusicTrackV1Response]:
    return await MetadataService(db).get_music_media_tracks(media_id)


@router.get("/metadata/music/tracks/{track_id}", response_model=MusicTrackV1Response)
async def get_music_track(track_id: UUID, db: DbSession) -> MusicTrackV1Response:
    return await MetadataService(db).get_music_track(track_id)
