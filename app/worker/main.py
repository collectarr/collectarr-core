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

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import (
    ImageAsset,
    MusicItem,
)
from app.models.catalog_boardgame_item import BoardGameItem
from app.models.catalog_book_item import BookItem
from app.models.catalog_game_item import GameItem
from app.models.catalog_comic_item import ComicItem
from app.models.catalog_movie_item import MovieItem
from app.models.catalog_manga_item import MangaItem
from app.models.catalog_anime_item import AnimeItem
from app.models.catalog_tv_item import TvItem
from app.search.client import SearchClient
from app.search.documents import (
    catalog_search_document,
    movie_item_search_document,
    music_item_search_document,
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
    root_tables = (
        BookItem,
        ComicItem,
        MangaItem,
        AnimeItem,
        MovieItem,
        TvItem,
        GameItem,
        BoardGameItem,
        MusicItem,
    )
    nested_fields = {
        BookItem: ("printings", "credits", "identifiers", "series_memberships"),
        ComicItem: ("identifiers",),
        MangaItem: ("identifiers",),
        AnimeItem: ("media", "episodes", "identifiers"),
        MovieItem: ("media",),
        TvItem: ("seasons", "media", "episodes", "identifiers"),
        GameItem: ("identifiers",),
        BoardGameItem: ("identifiers",),
        MusicItem: ("discs",),
    }
    item_count = 0
    item_updated_at: datetime | None = None
    edition_count = 0
    edition_updated_at: datetime | None = None

    for table in root_tables:
        count = await db.scalar(select(func.count()).select_from(table))
        updated_at = await db.scalar(select(func.max(table.updated_at)))
        item_count += count or 0
        if updated_at and (item_updated_at is None or updated_at > item_updated_at):
            item_updated_at = updated_at

    for model, fields in nested_fields.items():
        lengths = [
            func.coalesce(func.jsonb_array_length(model.details[field]), 0)
            for field in fields
        ]
        count = await db.scalar(
            select(func.coalesce(func.sum(sum(lengths)), 0)).select_from(model)
        )
        updated_at = await db.scalar(select(func.max(model.updated_at)))
        edition_count += count or 0
        if updated_at and (edition_updated_at is None or updated_at > edition_updated_at):
            edition_updated_at = updated_at

    return CatalogFingerprint(
        item_count=item_count,
        item_updated_at=item_updated_at,
        edition_count=edition_count,
        edition_updated_at=edition_updated_at,
        variant_count=0,
        variant_updated_at=None,
    )


async def index_once(search: SearchClient) -> None:
    async with AsyncSessionLocal() as db:
        documents = []
        book_rows = await db.execute(select(BookItem))
        documents.extend(catalog_search_document(row) for row in book_rows.scalars().unique())

        comic_rows = await db.execute(select(ComicItem))
        documents.extend(catalog_search_document(row) for row in comic_rows.scalars().unique())

        manga_rows = await db.execute(select(MangaItem))
        documents.extend(catalog_search_document(row) for row in manga_rows.scalars().unique())

        movie_rows = await db.execute(select(MovieItem))
        documents.extend(movie_item_search_document(row) for row in movie_rows.scalars().unique())

        tv_rows = await db.execute(select(TvItem))
        documents.extend(catalog_search_document(row) for row in tv_rows.scalars().unique())

        game_rows = await db.execute(select(GameItem))
        documents.extend(catalog_search_document(row) for row in game_rows.scalars().unique())

        boardgame_rows = await db.execute(select(BoardGameItem))
        documents.extend(catalog_search_document(row) for row in boardgame_rows.scalars().unique())

        anime_rows = await db.execute(select(AnimeItem))
        documents.extend(catalog_search_document(row) for row in anime_rows.scalars().unique())

        music_rows = await db.execute(
            select(MusicItem)
        )
        documents.extend(
            music_item_search_document(item)
            for item in music_rows.scalars().unique()
        )
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
