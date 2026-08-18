import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from time import monotonic

import imagehash
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import (
    AnimeCharacterAppearance,
    AnimeContribution,
    AnimeEpisode,
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookPrinting,
    BookSeriesMembership,
    BookWork,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIssue,
    ComicStoryArcMembership,
    ComicWork,
    GameRelease,
    GameWork,
    ImageAsset,
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaWork,
    MovieRelease,
    MovieReleaseMedia,
    MovieWork,
    MovieWorkContribution,
    MusicMedia,
    MusicRelease,
    MusicTrack,
    TVEpisode,
    TVRelease,
    TVReleaseContribution,
    TVReleaseMedia,
    TVSeason,
    TVSeries,
)
from app.search.client import SearchClient
from app.search.documents import (
    anime_series_search_document,
    boardgame_search_document,
    book_work_search_document,
    comic_work_search_document,
    game_work_search_document,
    manga_work_search_document,
    movie_work_search_document,
    tv_release_search_document,
)
from app.storage.client import ObjectStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CatalogFingerprint:
    item_count: int
    item_updated_at: datetime | None
    edition_count: int
    edition_updated_at: datetime | None
    variant_count: int
    variant_updated_at: datetime | None


def _compute_phash(image_data: bytes) -> str:
    with Image.open(BytesIO(image_data)) as pil_image:
        return str(imagehash.phash(pil_image))


async def catalog_fingerprint(db: AsyncSession) -> CatalogFingerprint:
    root_tables = (BookWork, ComicWork, MangaWork, AnimeSeries, MovieWork, TVSeries, GameWork, BoardGameWork, MusicRelease)
    edition_tables = (
        BookEdition,
        ComicIssue,
        MangaChapter,
        AnimeEpisode,
        MovieRelease,
        TVReleaseMedia,
        GameRelease,
        BoardGameEdition,
        MusicMedia,
    )
    variant_tables = (
        BookPrinting,
        TVReleaseEpisodeMap,
    )
    item_count = 0
    item_updated_at: datetime | None = None
    edition_count = 0
    edition_updated_at: datetime | None = None
    variant_count = 0
    variant_updated_at: datetime | None = None

    for table in root_tables:
        count = await db.scalar(select(func.count()).select_from(table))
        updated_at = await db.scalar(select(func.max(table.updated_at)))
        item_count += count or 0
        if updated_at and (item_updated_at is None or updated_at > item_updated_at):
            item_updated_at = updated_at

    for table in edition_tables:
        count = await db.scalar(select(func.count()).select_from(table))
        updated_at = await db.scalar(select(func.max(table.updated_at)))
        edition_count += count or 0
        if updated_at and (edition_updated_at is None or updated_at > edition_updated_at):
            edition_updated_at = updated_at

    for table in variant_tables:
        count = await db.scalar(select(func.count()).select_from(table))
        updated_at = await db.scalar(select(func.max(table.updated_at)))
        variant_count += count or 0
        if updated_at and (variant_updated_at is None or updated_at > variant_updated_at):
            variant_updated_at = updated_at

    return CatalogFingerprint(
        item_count=item_count,
        item_updated_at=item_updated_at,
        edition_count=edition_count,
        edition_updated_at=edition_updated_at,
        variant_count=variant_count,
        variant_updated_at=variant_updated_at,
    )


async def index_once(search: SearchClient) -> None:
    async with AsyncSessionLocal() as db:
        documents = []
        book_rows = await db.execute(
            select(BookWork).options(
                selectinload(BookWork.contributions).selectinload(BookContribution.person),
                selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
                selectinload(BookWork.series_memberships).selectinload(BookSeriesMembership.series),
                selectinload(BookWork.identifiers),
            )
        )
        documents.extend(book_work_search_document(row) for row in book_rows.scalars().unique())

        comic_rows = await db.execute(
            select(ComicWork).options(
                selectinload(ComicWork.contributions).selectinload(ComicContribution.person),
                selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                selectinload(ComicWork.series_memberships).selectinload(ComicSeriesMembership.series),
                selectinload(ComicWork.story_arc_memberships).selectinload(ComicStoryArcMembership.story_arc),
                selectinload(ComicWork.character_appearances).selectinload(ComicCharacterAppearance.character),
                selectinload(ComicWork.identifiers),
            )
        )
        documents.extend(comic_work_search_document(row) for row in comic_rows.scalars().unique())

        manga_rows = await db.execute(
            select(MangaWork).options(
                selectinload(MangaWork.contributions).selectinload(MangaContribution.person),
                selectinload(MangaWork.chapters).selectinload(MangaChapter.identifiers),
                selectinload(MangaWork.series_memberships).selectinload(MangaSeriesMembership.series),
                selectinload(MangaWork.character_appearances).selectinload(MangaCharacterAppearance.character),
                selectinload(MangaWork.identifiers),
            )
        )
        documents.extend(manga_work_search_document(row) for row in manga_rows.scalars().unique())

        movie_rows = await db.execute(
            select(MovieWork).options(
                selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
                selectinload(MovieWork.releases).selectinload(MovieRelease.media),
                selectinload(MovieWork.identifiers),
            )
        )
        documents.extend(movie_work_search_document(row) for row in movie_rows.scalars().unique())

        tv_rows = await db.execute(
            select(TVSeries).options(
                selectinload(TVSeries.releases).selectinload(TVRelease.contributions).selectinload(TVReleaseContribution.person),
                selectinload(TVSeries.releases).selectinload(TVRelease.identifiers),
                selectinload(TVSeries.releases).selectinload(TVRelease.media),
            )
        )
        documents.extend(tv_release_search_document(row) for row in tv_rows.scalars().unique())

        game_rows = await db.execute(select(GameWork).options(selectinload(GameWork.releases)))
        documents.extend(game_work_search_document(row) for row in game_rows.scalars().unique())

        boardgame_rows = await db.execute(select(BoardGameWork).options(selectinload(BoardGameWork.editions)))
        documents.extend(boardgame_search_document(row) for row in boardgame_rows.scalars().unique())

        anime_rows = await db.execute(
            select(AnimeSeries).options(
                selectinload(AnimeSeries.contributions).selectinload(AnimeContribution.person),
                selectinload(AnimeSeries.episodes),
                selectinload(AnimeSeries.identifiers),
                selectinload(AnimeSeries.character_appearances).selectinload(AnimeCharacterAppearance.character),
            )
        )
        documents.extend(anime_series_search_document(row) for row in anime_rows.scalars().unique())
        await search.index_documents(documents)


async def index_changed_catalog(
    search: SearchClient,
    last_fingerprint: CatalogFingerprint | None,
) -> CatalogFingerprint | None:
    async with AsyncSessionLocal() as db:
        current_fingerprint = await catalog_fingerprint(db)
    if current_fingerprint == last_fingerprint:
        return last_fingerprint

    try:
        await index_once(search)
    except Exception as exc:
        logger.exception(
            "worker_index_failed items=%s editions=%s variants=%s error=%s",
            current_fingerprint.item_count,
            current_fingerprint.edition_count,
            current_fingerprint.variant_count,
            exc,
        )
        return last_fingerprint

    logger.info(
        "worker_index_finished items=%s editions=%s variants=%s",
        current_fingerprint.item_count,
        current_fingerprint.edition_count,
        current_fingerprint.variant_count,
    )
    return current_fingerprint


async def backfill_cover_phashes(limit: int = 50) -> int:
    """Compute perceptual hashes for image assets with NULL phash."""
    storage = ObjectStorage.shared()
    updated = 0
    try:
        async with AsyncSessionLocal() as db:
            result = await db.scalars(
                select(ImageAsset)
                .where(
                    ImageAsset.phash.is_(None),
                    ImageAsset.storage_key.is_not(None),
                )
                .limit(limit)
            )
            assets = result.all()
            if not assets:
                return 0

            for asset in assets:
                try:
                    body, _ = await asyncio.to_thread(
                        storage.get_object, asset.storage_key
                    )
                    asset.phash = await asyncio.to_thread(_compute_phash, body)
                    updated += 1
                except Exception:
                    logger.debug(
                        "phash_backfill_skip asset_id=%s key=%s",
                        asset.id,
                        asset.storage_key,
                        exc_info=True,
                    )
            if updated:
                await db.commit()
    except Exception:
        logger.exception("worker_phash_backfill_failed limit=%s", limit)
        return 0

    if updated:
        logger.info("worker_phash_backfill_finished updated=%s", updated)
    return updated


async def main() -> None:
    settings = get_settings()
    search = SearchClient()
    logger.info(
        "worker_starting index_interval_seconds=%s",
        settings.worker_index_interval_seconds,
    )
    await search.configure()
    ObjectStorage().ensure_bucket()
    last_fingerprint: CatalogFingerprint | None = None
    next_index_run_at = 0.0
    next_phash_run_at = 0.0

    while True:
        now = monotonic()
        if now >= next_index_run_at:
            last_fingerprint = await index_changed_catalog(search, last_fingerprint)
            next_index_run_at = monotonic() + settings.worker_index_interval_seconds

        if now >= next_phash_run_at:
            await backfill_cover_phashes(limit=50)
            next_phash_run_at = monotonic() + settings.worker_index_interval_seconds

        sleep_until = min(next_index_run_at, next_phash_run_at)
        await asyncio.sleep(max(1.0, sleep_until - monotonic()))


if __name__ == "__main__":
    asyncio.run(main())
