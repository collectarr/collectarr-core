import logging
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    ExternalProviderId,
)
from app.models.base import ExternalProvider, ItemKind
from app.providers.registry import ProviderRegistry
from app.schemas import (
    AnimeEpisodeV1Response,
    AnimeSeriesV1Response,
    BoardGameEditionV1Response,
    BoardGameWorkV1Response,
    BookEditionV1Response,
    BookWorkV1Response,
    ComicIssueV1Response,
    ComicWorkV1Response,
    ExternalProviderIdResponse,
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
    TVReleaseEpisodeMapV1Response,
    TVReleaseMediaResponse,
    TVReleaseV1Response,
    TVSeriesV1Response,
)
from app.schemas.metadata_shared import SearchResult
from app.search.client import SearchClient
from app.services.facade import MetadataFacade
from app.services.metadata_response_builders import MetadataResponseBuilders
from app.services.metadata_search_service import MetadataSearchService
from app.services.metadata_typed_reads import MetadataTypedReadService
from app.services.provider_search_state import ProviderSearchState

logger = logging.getLogger(__name__)

_UPSTREAM_HTTP_STATUS_RE = re.compile(r"\bHTTP\s+(?P<status>\d{3})\b")
_PROVIDER_INTERNAL_RETRY_NAMES = {ExternalProvider.bgg.value, ExternalProvider.comicvine.value}


class MetadataService(MetadataFacade, MetadataResponseBuilders):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.search_client = SearchClient()
        self.providers = ProviderRegistry()
        self.provider_search_state = ProviderSearchState(self.settings)
        self.typed_reads = MetadataTypedReadService(self)
        self.search_service = MetadataSearchService(self)

    async def get_book_work(self, work_id: UUID) -> BookWorkV1Response:
        return await self.typed_reads.get_book_work(work_id)

    async def get_book_work_editions(self, work_id: UUID) -> list[BookEditionV1Response]:
        return await self.typed_reads.get_book_work_editions(work_id)

    async def get_book_edition(self, edition_id: UUID) -> BookEditionV1Response:
        return await self.typed_reads.get_book_edition(edition_id)

    async def get_game_work(self, work_id: UUID) -> GameWorkV1Response:
        return await self.typed_reads.get_game_work(work_id)

    async def get_game_work_releases(self, work_id: UUID) -> list[GameReleaseV1Response]:
        return await self.typed_reads.get_game_work_releases(work_id)

    async def get_game_release(self, release_id: UUID) -> GameReleaseV1Response:
        return await self.typed_reads.get_game_release(release_id)

    async def get_boardgame_work(self, work_id: UUID) -> BoardGameWorkV1Response:
        return await self.typed_reads.get_boardgame_work(work_id)

    async def get_boardgame_work_editions(
        self, work_id: UUID
    ) -> list[BoardGameEditionV1Response]:
        return await self.typed_reads.get_boardgame_work_editions(work_id)

    async def get_boardgame_edition(self, edition_id: UUID) -> BoardGameEditionV1Response:
        return await self.typed_reads.get_boardgame_edition(edition_id)

    async def get_comic_work(self, work_id: UUID) -> ComicWorkV1Response:
        return await self.typed_reads.get_comic_work(work_id)

    async def get_comic_work_issues(self, work_id: UUID) -> list[ComicIssueV1Response]:
        return await self.typed_reads.get_comic_work_issues(work_id)

    async def get_comic_issue(self, issue_id: UUID) -> ComicIssueV1Response:
        return await self.typed_reads.get_comic_issue(issue_id)

    async def get_manga_work(self, work_id: UUID) -> MangaWorkV1Response:
        return await self.typed_reads.get_manga_work(work_id)

    async def get_manga_work_chapters(self, work_id: UUID) -> list[MangaChapterV1Response]:
        return await self.typed_reads.get_manga_work_chapters(work_id)

    async def get_manga_chapter(self, chapter_id: UUID) -> MangaChapterV1Response:
        return await self.typed_reads.get_manga_chapter(chapter_id)

    async def get_anime_series(self, series_id: UUID) -> AnimeSeriesV1Response:
        return await self.typed_reads.get_anime_series(series_id)

    async def get_anime_series_episodes(self, series_id: UUID) -> list[AnimeEpisodeV1Response]:
        return await self.typed_reads.get_anime_series_episodes(series_id)

    async def get_anime_episode(self, episode_id: UUID) -> AnimeEpisodeV1Response:
        return await self.typed_reads.get_anime_episode(episode_id)

    async def get_movie_work(self, work_id: UUID) -> MovieWorkV1Response:
        return await self.typed_reads.get_movie_work(work_id)

    async def get_movie_work_releases(self, work_id: UUID) -> list[MovieReleaseV1Response]:
        return await self.typed_reads.get_movie_work_releases(work_id)

    async def get_movie_release(self, release_id: UUID) -> MovieReleaseV1Response:
        return await self.typed_reads.get_movie_release(release_id)

    async def get_music_release(self, release_id: UUID) -> MusicReleaseV1Response:
        return await self.typed_reads.get_music_release(release_id)

    async def get_music_release_media(self, release_id: UUID) -> list[MusicMediaV1Response]:
        return await self.typed_reads.get_music_release_media(release_id)

    async def get_music_media(self, media_id: UUID) -> MusicMediaV1Response:
        return await self.typed_reads.get_music_media(media_id)

    async def get_music_media_tracks(self, media_id: UUID) -> list[MusicTrackV1Response]:
        return await self.typed_reads.get_music_media_tracks(media_id)

    async def get_music_track(self, track_id: UUID) -> MusicTrackV1Response:
        return await self.typed_reads.get_music_track(track_id)

    async def get_tv_series(self, series_id: UUID) -> TVSeriesV1Response:
        return await self.typed_reads.get_tv_series(series_id)

    async def get_tv_series_seasons(self, series_id: UUID) -> list[TVSeasonV1Response]:
        return await self.typed_reads.get_tv_series_seasons(series_id)

    async def get_tv_series_releases(self, series_id: UUID) -> list[TVReleaseV1Response]:
        return await self.typed_reads.get_tv_series_releases(series_id)

    async def get_tv_season(self, season_id: UUID) -> TVSeasonV1Response:
        return await self.typed_reads.get_tv_season(season_id)

    async def get_tv_season_episodes(self, season_id: UUID) -> list[TVEpisodeV1Response]:
        return await self.typed_reads.get_tv_season_episodes(season_id)

    async def get_tv_release(self, release_id: UUID) -> TVReleaseV1Response:
        return await self.typed_reads.get_tv_release(release_id)

    async def get_tv_release_media(self, release_id: UUID) -> list[TVReleaseMediaResponse]:
        return await self.typed_reads.get_tv_release_media(release_id)

    async def get_tv_release_episode_map(
        self, release_id: UUID
    ) -> list[TVReleaseEpisodeMapV1Response]:
        return await self.typed_reads.get_tv_release_episode_map(release_id)

    async def get_tv_release_media_item(self, media_id: UUID) -> TVReleaseMediaResponse:
        return await self.typed_reads.get_tv_release_media_item(media_id)

    async def get_tv_episode(self, episode_id: UUID) -> TVEpisodeV1Response:
        return await self.typed_reads.get_tv_episode(episode_id)

    async def _provider_links_for_entity(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> list[ExternalProviderIdResponse]:
        result = await self.db.execute(
            select(ExternalProviderId)
            .where(
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.entity_id == entity_id,
            )
            .order_by(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
        )
        return [
            ExternalProviderIdResponse(
                provider=row.provider,
                entity_type=row.entity_type,
                provider_item_id=row.provider_item_id,
                site_url=row.site_url,
                api_url=row.api_url,
            )
            for row in result.scalars()
        ]

    async def search(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        imprint: str | None = None,
        subtitle: str | None = None,
        series_group: str | None = None,
        language: str | None = None,
        country: str | None = None,
        age_rating: str | None = None,
        catalog_number: str | None = None,
        release_status: str | None = None,
        year: int | None = None,
        barcode: str | None = None,
        limit: int = 25,
    ) -> list[SearchResult]:
        return await self.search_service.search(
            query=query,
            kind=kind,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            imprint=imprint,
            subtitle=subtitle,
            series_group=series_group,
            language=language,
            country=country,
            age_rating=age_rating,
            catalog_number=catalog_number,
            release_status=release_status,
            year=year,
            barcode=barcode,
            limit=limit,
        )

    async def lookup_barcode(self, barcode: str, kind: ItemKind | None = None) -> SearchResult:
        return await self.search_service.lookup_barcode(barcode, kind)
