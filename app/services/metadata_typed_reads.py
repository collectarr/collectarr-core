from __future__ import annotations

from uuid import UUID

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
from app.services.metadata_reads import (
    get_anime_episode as _get_anime_episode,
)
from app.services.metadata_reads import (
    get_anime_series as _get_anime_series,
)
from app.services.metadata_reads import (
    get_anime_series_episodes as _get_anime_series_episodes,
)
from app.services.metadata_reads import (
    get_boardgame_edition as _get_boardgame_edition,
)
from app.services.metadata_reads import (
    get_boardgame_work as _get_boardgame_work,
)
from app.services.metadata_reads import (
    get_boardgame_work_editions as _get_boardgame_work_editions,
)
from app.services.metadata_reads import (
    get_book_edition as _get_book_edition,
)
from app.services.metadata_reads import (
    get_book_work as _get_book_work,
)
from app.services.metadata_reads import (
    get_book_work_editions as _get_book_work_editions,
)
from app.services.metadata_reads import (
    get_comic_issue as _get_comic_issue,
)
from app.services.metadata_reads import (
    get_comic_work as _get_comic_work,
)
from app.services.metadata_reads import (
    get_comic_work_issues as _get_comic_work_issues,
)
from app.services.metadata_reads import (
    get_game_release as _get_game_release,
)
from app.services.metadata_reads import (
    get_game_work as _get_game_work,
)
from app.services.metadata_reads import (
    get_game_work_releases as _get_game_work_releases,
)
from app.services.metadata_reads import (
    get_manga_chapter as _get_manga_chapter,
)
from app.services.metadata_reads import (
    get_manga_work as _get_manga_work,
)
from app.services.metadata_reads import (
    get_manga_work_chapters as _get_manga_work_chapters,
)
from app.services.metadata_reads import (
    get_movie_release as _get_movie_release,
)
from app.services.metadata_reads import (
    get_movie_work as _get_movie_work,
)
from app.services.metadata_reads import (
    get_movie_work_releases as _get_movie_work_releases,
)
from app.services.metadata_reads import (
    get_music_media as _get_music_media,
)
from app.services.metadata_reads import (
    get_music_media_tracks as _get_music_media_tracks,
)
from app.services.metadata_reads import (
    get_music_release as _get_music_release,
)
from app.services.metadata_reads import (
    get_music_release_media as _get_music_release_media,
)
from app.services.metadata_reads import (
    get_music_track as _get_music_track,
)
from app.services.metadata_reads import (
    get_tv_episode as _get_tv_episode,
)
from app.services.metadata_reads import (
    get_tv_series as _get_tv_series,
)
from app.services.metadata_reads import (
    get_tv_series_seasons as _get_tv_series_seasons,
)


class MetadataTypedReadService:
    def __init__(self, service) -> None:
        self.service = service

    async def get_book_work(self, work_id: UUID) -> BookWorkV1Response:
        return await _get_book_work(self.service, work_id)

    async def get_book_work_editions(self, work_id: UUID) -> list[BookEditionV1Response]:
        return await _get_book_work_editions(self.service, work_id)

    async def get_book_edition(self, edition_id: UUID) -> BookEditionV1Response:
        return await _get_book_edition(self.service, edition_id)

    async def get_game_work(self, work_id: UUID) -> GameWorkV1Response:
        return await _get_game_work(self.service, work_id)

    async def get_game_work_releases(self, work_id: UUID) -> list[GameReleaseV1Response]:
        return await _get_game_work_releases(self.service, work_id)

    async def get_game_release(self, release_id: UUID) -> GameReleaseV1Response:
        return await _get_game_release(self.service, release_id)

    async def get_boardgame_work(self, work_id: UUID) -> BoardGameWorkV1Response:
        return await _get_boardgame_work(self.service, work_id)

    async def get_boardgame_work_editions(self, work_id: UUID) -> list[BoardGameEditionV1Response]:
        return await _get_boardgame_work_editions(self.service, work_id)

    async def get_boardgame_edition(self, edition_id: UUID) -> BoardGameEditionV1Response:
        return await _get_boardgame_edition(self.service, edition_id)

    async def get_comic_work(self, work_id: UUID) -> ComicWorkV1Response:
        return await _get_comic_work(self.service, work_id)

    async def get_comic_work_issues(self, work_id: UUID) -> list[ComicIssueV1Response]:
        return await _get_comic_work_issues(self.service, work_id)

    async def get_comic_issue(self, issue_id: UUID) -> ComicIssueV1Response:
        return await _get_comic_issue(self.service, issue_id)

    async def get_manga_work(self, work_id: UUID) -> MangaWorkV1Response:
        return await _get_manga_work(self.service, work_id)

    async def get_manga_work_chapters(self, work_id: UUID) -> list[MangaChapterV1Response]:
        return await _get_manga_work_chapters(self.service, work_id)

    async def get_manga_chapter(self, chapter_id: UUID) -> MangaChapterV1Response:
        return await _get_manga_chapter(self.service, chapter_id)

    async def get_anime_series(self, series_id: UUID) -> AnimeSeriesV1Response:
        return await _get_anime_series(self.service, series_id)

    async def get_anime_series_episodes(self, series_id: UUID) -> list[AnimeEpisodeV1Response]:
        return await _get_anime_series_episodes(self.service, series_id)

    async def get_anime_episode(self, episode_id: UUID) -> AnimeEpisodeV1Response:
        return await _get_anime_episode(self.service, episode_id)

    async def get_movie_work(self, work_id: UUID) -> MovieWorkV1Response:
        return await _get_movie_work(self.service, work_id)

    async def get_movie_work_releases(self, work_id: UUID) -> list[MovieReleaseV1Response]:
        return await _get_movie_work_releases(self.service, work_id)

    async def get_movie_release(self, release_id: UUID) -> MovieReleaseV1Response:
        return await _get_movie_release(self.service, release_id)

    async def get_music_release(self, release_id: UUID) -> MusicReleaseV1Response:
        return await _get_music_release(self.service, release_id)

    async def get_music_release_media(self, release_id: UUID) -> list[MusicMediaV1Response]:
        return await _get_music_release_media(self.service, release_id)

    async def get_music_media(self, media_id: UUID) -> MusicMediaV1Response:
        return await _get_music_media(self.service, media_id)

    async def get_music_media_tracks(self, media_id: UUID) -> list[MusicTrackV1Response]:
        return await _get_music_media_tracks(self.service, media_id)

    async def get_music_track(self, track_id: UUID) -> MusicTrackV1Response:
        return await _get_music_track(self.service, track_id)

    async def get_tv_series(self, series_id: UUID) -> TVSeriesV1Response:
        return await _get_tv_series(self.service, series_id)

    async def get_tv_series_seasons(self, series_id: UUID) -> list[TVSeasonV1Response]:
        return await _get_tv_series_seasons(self.service, series_id)

    async def get_tv_episode(self, episode_id: UUID) -> TVEpisodeV1Response:
        return await _get_tv_episode(self.service, episode_id)
