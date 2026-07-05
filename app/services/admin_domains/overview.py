import logging
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AdminAuditLog,
    AnimeCharacterAppearance,
    AnimeContribution,
    AnimeEpisode,
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookPrinting,
    BookSeries,
    BookSeriesMembership,
    BookWork,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIssue,
    ComicSeries,
    ComicStoryArcMembership,
    ComicVolume,
    ComicWork,
    ExternalProviderId,
    GameRelease,
    GameWork,
    ImageAsset,
    ImageCacheEntry,
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaSeries,
    MangaSeriesMembership,
    MangaWork,
    MetadataProposal,
    MovieRelease,
    MovieReleaseMedia,
    MovieWork,
    MovieWorkContribution,
    MusicMedia,
    MusicRelease,
    MusicTrack,
    ProviderIngestJob,
    TVRelease,
    TVReleaseContribution,
    TVReleaseMedia,
    TVSeason,
    TVSeries,
)
from app.models.base import ItemKind
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminCatalogSummaryResponse,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
    ProviderCacheStatsResponse,
    ProviderCacheSummaryResponse,
    ProviderIngestHistoryEntry,
    ProviderStatusResponse,
)
from app.search.client import SearchClient
from app.search.documents import catalog_search_document

_SEARCH_HISTORY: deque[AdminSearchHistoryEntry] = deque(maxlen=20)
logger = logging.getLogger(__name__)


def _meili_document_count(stats: Any) -> int | None:
    if isinstance(stats, dict):
        value = stats.get("numberOfDocuments")
        if value is None:
            value = stats.get("number_of_documents")
    else:
        value = getattr(stats, "number_of_documents", None)
        if value is None:
            value = getattr(stats, "numberOfDocuments", None)
        if value is None and hasattr(stats, "model_dump"):
            dumped = stats.model_dump(by_alias=True)
            value = dumped.get("numberOfDocuments")
            if value is None:
                value = dumped.get("number_of_documents")
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            return None
    return value if isinstance(value, int) else None


class AdminOverviewService:
    def __init__(
        self,
        *,
        db: AsyncSession,
        settings: Any,
        providers: Any,
        search_client_cls: type[SearchClient] | None = None,
        provider_search_state: Any,
        provider_preview_state: Any,
        duplicate_group_count: Callable[[], Awaitable[int]],
        ingest_history_reader: Callable[[], list[ProviderIngestHistoryEntry]],
    ) -> None:
        self.db = db
        self.settings = settings
        self.providers = providers
        self.search_client_cls = search_client_cls or SearchClient
        self.provider_search_state = provider_search_state
        self.provider_preview_state = provider_preview_state
        self._duplicate_group_count = duplicate_group_count
        self._ingest_history_reader = ingest_history_reader

    async def provider_statuses(self) -> list[ProviderStatusResponse]:
        return [
            ProviderStatusResponse(
                name=status.name,
                display_name=status.display_name,
                kind=status.kind.value,
                supported_kinds=[kind.value for kind in status.supported_kinds],
                status="live" if status.is_configured else "stub",
                is_configured=status.is_configured,
                supports_search=status.supports_search,
                supports_ingest=status.supports_ingest,
                requires_user_key=status.requires_user_key,
                non_commercial_only=status.non_commercial_only,
                allows_redistribution=status.allows_redistribution,
                allows_image_mirroring=status.allows_image_mirroring,
                image_policy=status.image_policy,
                requires_attribution=status.requires_attribution,
                license_name=status.license_name,
                terms_url=status.terms_url,
                attribution_url=status.attribution_url,
                rate_limit=status.rate_limit,
                cache_policy=status.cache_policy,
                message=status.status_message,
            )
            for status in self.providers.status_entries_for_settings(self.settings)
        ]

    async def provider_cache_stats(self) -> ProviderCacheSummaryResponse:
        return ProviderCacheSummaryResponse(
            search=ProviderCacheStatsResponse(**(await self.provider_search_state.stats())),
            preview=ProviderCacheStatsResponse(**(await self.provider_preview_state.stats())),
        )

    async def catalog_summary(self) -> AdminCatalogSummaryResponse:
        duplicate_groups = await self._duplicate_group_count()
        items_by_kind = await self._item_counts_by_kind()
        return AdminCatalogSummaryResponse(
            items=sum(items_by_kind.values()),
            items_by_kind=items_by_kind,
            series=(
                await self._count(BookSeries)
                + await self._count(ComicSeries)
                + await self._count(MangaSeries)
                + await self._count(AnimeSeries)
            ),
            volumes=await self._count(ComicVolume),
            editions=(
                await self._count(BookEdition)
                + await self._count(ComicIssue)
                + await self._count(MangaChapter)
                + await self._count(AnimeEpisode)
                + await self._count(MovieRelease)
                + await self._count(TVSeries)
                + await self._count(GameRelease)
                + await self._count(BoardGameEdition)
                + await self._count(MusicMedia)
            ),
            variants=(
                await self._count(BookPrinting)
                + await self._count(MovieReleaseMedia)
                + await self._count(MusicTrack)
            ),
            provider_links=await self._provider_link_count(),
            image_assets=await self._count_image_assets(),
            image_cache_entries=await self._count(ImageCacheEntry),
            pending_proposals=await self._count_pending_proposals(),
            missing_cover_items=await self._count_missing_cover_items(),
            missing_provider_link_items=await self._count_missing_provider_link_items(),
            duplicate_candidate_groups=duplicate_groups,
            provider_ingest_successes=await self._provider_ingest_success_count(),
            provider_ingest_failures=await self._provider_ingest_failure_count(),
        )

    async def search_status(self) -> AdminSearchStatusResponse:
        try:
            client = self.search_client_cls()
            client.client.health()
            stats = client.client.index(client.index_name).get_stats()
            document_count = _meili_document_count(stats)
        except Exception as exc:
            logger.warning("admin_search_status_failed error=%s", exc)
            return AdminSearchStatusResponse(
                ok=False,
                index_name=self.search_client_cls.index_name,
                error=str(exc),
            )
        return AdminSearchStatusResponse(
            ok=True,
            index_name=client.index_name,
            document_count=document_count,
            is_empty=document_count == 0 if document_count is not None else None,
        )

    async def reindex_search(self) -> AdminSearchReindexResponse:
        search = self.search_client_cls()
        try:
            await search.configure()
            documents = await self._search_documents()
            await search.replace_documents(documents)
        except Exception as exc:
            logger.warning("admin_search_reindex_failed index=%s error=%s", search.index_name, exc)
            response = AdminSearchReindexResponse(
                ok=False,
                index_name=search.index_name,
                indexed_documents=0,
                error=str(exc),
            )
            self._record_search_history(response)
            return response
        response = AdminSearchReindexResponse(
            ok=True,
            index_name=search.index_name,
            indexed_documents=len(documents),
        )
        self._record_search_history(response)
        return response

    def search_history(self) -> list[AdminSearchHistoryEntry]:
        return list(_SEARCH_HISTORY)

    async def audit_logs(
        self,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        limit: int = 25,
    ) -> list[AdminAuditLogResponse]:
        stmt = select(AdminAuditLog).order_by(
            AdminAuditLog.created_at.desc(),
            AdminAuditLog.id.desc(),
        )
        if action:
            stmt = stmt.where(AdminAuditLog.action == action)
        if entity_type:
            stmt = stmt.where(AdminAuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AdminAuditLog.entity_id == entity_id)
        result = await self.db.execute(stmt.limit(limit))
        return [AdminAuditLogResponse.model_validate(row) for row in result.scalars()]

    async def _count(self, model: type) -> int:
        return int(await self.db.scalar(select(func.count()).select_from(model)) or 0)

    async def _item_counts_by_kind(self) -> dict[str, int]:
        counts = {kind.value: 0 for kind in ItemKind}
        native_counts: dict[ItemKind, type] = {
            ItemKind.book: BookWork,
            ItemKind.comic: ComicWork,
            ItemKind.manga: MangaWork,
            ItemKind.anime: AnimeSeries,
            ItemKind.movie: MovieWork,
            ItemKind.tv: TVSeries,
            ItemKind.music: MusicRelease,
            ItemKind.game: GameWork,
            ItemKind.boardgame: BoardGameWork,
        }
        for kind, model in native_counts.items():
            counts[kind.value] = await self._count(model)
        return counts

    async def _count_image_assets(self) -> int:
        return await self._count(ImageAsset)

    async def _count_pending_proposals(self) -> int:
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(MetadataProposal)
                .where(MetadataProposal.status == "pending")
            )
            or 0
        )

    async def _count_missing_cover_items(self) -> int:
        total = 0
        total += await self._count_missing_cover_items_for_child(BookWork, BookEdition, "work_id")
        total += await self._count_missing_cover_items_for_child(ComicWork, ComicIssue, "work_id")
        total += await self._count_missing_cover_items_for_child(MangaWork, MangaChapter, "work_id")
        total += await self._count_missing_cover_items_for_child(AnimeSeries, AnimeEpisode, "series_id")
        total += await self._count_missing_cover_items_for_child(
            MovieWork,
            MovieRelease,
            "work_id",
            root_cover_fields=("poster_image_url", "poster_image_key"),
        )
        total += await self._count_missing_cover_items_for_root(
            TVRelease,
            cover_fields=("cover_image_url", "cover_image_key"),
        )
        total += await self._count_missing_cover_items_for_child(
            GameWork,
            GameRelease,
            "work_id",
            root_cover_fields=("cover_image_url", "cover_image_key"),
        )
        total += await self._count_missing_cover_items_for_child(
            BoardGameWork,
            BoardGameEdition,
            "work_id",
            root_cover_fields=("cover_image_url", "cover_image_key"),
        )
        total += await self._count_missing_cover_items_for_root(
            MusicRelease,
            cover_fields=("cover_image_url", "cover_image_key"),
        )
        return total

    async def _count_missing_provider_link_items(self) -> int:
        total = await self._count_missing_provider_links_for_entity("book_work", BookWork)
        total += await self._count_missing_provider_links_for_entity("comic_work", ComicWork)
        total += await self._count_missing_provider_links_for_entity("manga_work", MangaWork)
        total += await self._count_missing_provider_links_for_entity("anime_series", AnimeSeries)
        total += await self._count_missing_provider_links_for_entity("movie_work", MovieWork)
        total += await self._count_missing_provider_links_for_entity("tv_series", TVSeries)
        total += await self._count_missing_provider_links_for_entity("game_work", GameWork)
        total += await self._count_missing_provider_links_for_entity("boardgame_work", BoardGameWork)
        return total

    async def _provider_link_count(self) -> int:
        return await self._count(ExternalProviderId)

    async def _count_missing_provider_links_for_entity(self, entity_type: str, model: type) -> int:
        has_provider_link = exists().where(
            ExternalProviderId.entity_type == entity_type,
            ExternalProviderId.entity_id == model.id,
        )
        return int(await self.db.scalar(select(func.count()).select_from(model).where(~has_provider_link)) or 0)

    async def _count_missing_cover_items_for_root(
        self,
        model: type,
        *,
        cover_fields: tuple[str, str] = ("cover_image_url", "cover_image_key"),
    ) -> int:
        has_cover = or_(*[getattr(model, field).is_not(None) for field in cover_fields])
        return int(await self.db.scalar(select(func.count()).select_from(model).where(~has_cover)) or 0)

    async def _count_missing_cover_items_for_child(
        self,
        parent_model: type,
        child_model: type,
        parent_fk: str,
        *,
        root_cover_fields: tuple[str, str] = (),
        child_cover_fields: tuple[str, str] = ("cover_image_url", "cover_image_key"),
    ) -> int:
        root_has_cover = (
            or_(*[getattr(parent_model, field).is_not(None) for field in root_cover_fields])
            if root_cover_fields
            else None
        )
        child_has_cover = exists().where(
            getattr(child_model, parent_fk) == parent_model.id,
            or_(*[getattr(child_model, field).is_not(None) for field in child_cover_fields]),
        )
        predicate = child_has_cover if root_has_cover is None else or_(root_has_cover, child_has_cover)
        return int(await self.db.scalar(select(func.count()).select_from(parent_model).where(~predicate)) or 0)

    async def _search_documents(self) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []

        book_result = await self.db.execute(
            select(BookWork).options(
                selectinload(BookWork.editions).selectinload(BookEdition.contributions).selectinload(
                    BookContribution.person
                ),
                selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
                selectinload(BookWork.series_memberships).selectinload(BookSeriesMembership.series),
            )
        )
        documents.extend(catalog_search_document(work) for work in book_result.scalars().unique())

        comic_result = await self.db.execute(
            select(ComicWork).options(
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.contributions)
                .selectinload(ComicContribution.person),
                selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.character_appearances)
                .selectinload(ComicCharacterAppearance.character),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.story_arc_memberships)
                .selectinload(ComicStoryArcMembership.story_arc),
            )
        )
        documents.extend(catalog_search_document(work) for work in comic_result.scalars().unique())

        manga_result = await self.db.execute(
            select(MangaWork).options(
                selectinload(MangaWork.chapters),
                selectinload(MangaWork.contributions).selectinload(MangaContribution.person),
                selectinload(MangaWork.character_appearances).selectinload(MangaCharacterAppearance.character),
                selectinload(MangaWork.series_memberships).selectinload(MangaSeriesMembership.series),
            )
        )
        documents.extend(catalog_search_document(work) for work in manga_result.scalars().unique())

        anime_result = await self.db.execute(
            select(AnimeSeries).options(
                selectinload(AnimeSeries.episodes),
                selectinload(AnimeSeries.contributions).selectinload(AnimeContribution.person),
                selectinload(AnimeSeries.character_appearances).selectinload(AnimeCharacterAppearance.character),
            )
        )
        documents.extend(catalog_search_document(series) for series in anime_result.scalars().unique())

        movie_result = await self.db.execute(
            select(MovieWork).options(
                selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
                selectinload(MovieWork.releases),
                selectinload(MovieWork.identifiers),
            )
        )
        documents.extend(catalog_search_document(work) for work in movie_result.scalars().unique())

        tv_result = await self.db.execute(
            select(TVSeries).options(
                selectinload(TVSeries.seasons).selectinload(TVSeason.episodes),
                selectinload(TVSeries.releases).selectinload(TVRelease.contributions).selectinload(
                    TVReleaseContribution.person
                ),
                selectinload(TVSeries.releases).selectinload(TVReleaseMedia.episodes),
                selectinload(TVSeries.releases).selectinload(TVRelease.identifiers),
            )
        )
        documents.extend(catalog_search_document(release) for release in tv_result.scalars().unique())

        game_result = await self.db.execute(select(GameWork).options(selectinload(GameWork.releases)))
        documents.extend(catalog_search_document(work) for work in game_result.scalars().unique())

        boardgame_result = await self.db.execute(select(BoardGameWork).options(selectinload(BoardGameWork.editions)))
        documents.extend(catalog_search_document(work) for work in boardgame_result.scalars().unique())

        return documents

    def _record_search_history(self, response: AdminSearchReindexResponse) -> None:
        _SEARCH_HISTORY.appendleft(
            AdminSearchHistoryEntry(
                timestamp=datetime.now(UTC),
                ok=response.ok,
                index_name=response.index_name,
                indexed_documents=response.indexed_documents,
                error=response.error,
            )
        )

    async def _provider_ingest_success_count(self) -> int:
        job_count = await self._count_ingest_jobs("done")
        memory_count = sum(
            1 for entry in self._ingest_history_reader() if entry.status in {"created", "existing"}
        )
        return job_count + memory_count

    async def _provider_ingest_failure_count(self) -> int:
        job_count = await self._count_ingest_jobs("failed")
        memory_count = sum(1 for entry in self._ingest_history_reader() if entry.status == "failed")
        return job_count + memory_count

    async def _count_ingest_jobs(self, status_filter: str) -> int:
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(ProviderIngestJob)
                .where(ProviderIngestJob.status == status_filter)
            )
            or 0
        )