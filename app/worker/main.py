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
from app.models import CanonicalCatalogItem, ImageAsset
from app.search.catalog_item_documents import catalog_item_search_document
from app.search.client import SearchClient
from app.storage.client import ObjectStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CatalogFingerprint:
    item_count: int
    item_updated_at: datetime | None


def _compute_phash(image_data: bytes) -> str:
    with Image.open(BytesIO(image_data)) as image:
        return str(imagehash.phash(image))


async def catalog_fingerprint(db: AsyncSession) -> CatalogFingerprint:
    count = int(
        await db.scalar(select(func.count()).select_from(CanonicalCatalogItem)) or 0
    )
    updated_at = await db.scalar(select(func.max(CanonicalCatalogItem.updated_at)))
    return CatalogFingerprint(item_count=count, item_updated_at=updated_at)


async def index_once(search: SearchClient) -> None:
    async with AsyncSessionLocal() as db:
        rows = await db.scalars(
            select(CanonicalCatalogItem).order_by(
                CanonicalCatalogItem.kind.asc(),
                CanonicalCatalogItem.sort_title.asc().nullslast(),
                CanonicalCatalogItem.title.asc(),
                CanonicalCatalogItem.id.asc(),
            )
        )
        documents = [catalog_item_search_document(item) for item in rows]
    await search.replace_documents(documents)


async def index_changed_catalog(
    search: SearchClient,
    last_fingerprint: CatalogFingerprint | None,
) -> CatalogFingerprint | None:
    async with AsyncSessionLocal() as db:
        current = await catalog_fingerprint(db)
    if current == last_fingerprint:
        return last_fingerprint
    try:
        await index_once(search)
    except Exception:
        logger.exception("catalog_item_index_failed count=%s", current.item_count)
        return last_fingerprint
    logger.info("catalog_item_index_finished count=%s", current.item_count)
    return current


async def backfill_cover_phashes(limit: int = 50) -> int:
    """Compute perceptual hashes for uploaded images that do not have one."""
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
            for asset in result.all():
                try:
                    body, _ = await asyncio.to_thread(
                        storage.get_object, asset.storage_key
                    )
                    asset.phash = await asyncio.to_thread(_compute_phash, body)
                    updated += 1
                except Exception:
                    logger.debug(
                        "phash_backfill_skip asset_id=%s",
                        asset.id,
                        exc_info=True,
                    )
            if updated:
                await db.commit()
    except Exception:
        logger.exception("phash_backfill_failed limit=%s", limit)
        return 0
    if updated:
        logger.info("phash_backfill_finished updated=%s", updated)
    return updated


async def main() -> None:
    settings = get_settings()
    search = SearchClient()
    await search.configure()
    ObjectStorage().ensure_bucket()
    logger.info(
        "worker_starting index_interval_seconds=%s",
        settings.worker_index_interval_seconds,
    )
    fingerprint: CatalogFingerprint | None = None
    next_index_run_at = 0.0
    next_phash_run_at = 0.0
    while True:
        now = monotonic()
        if now >= next_index_run_at:
            fingerprint = await index_changed_catalog(search, fingerprint)
            next_index_run_at = monotonic() + settings.worker_index_interval_seconds
        if now >= next_phash_run_at:
            await backfill_cover_phashes()
            next_phash_run_at = monotonic() + settings.worker_index_interval_seconds
        await asyncio.sleep(max(1.0, min(next_index_run_at, next_phash_run_at) - monotonic()))


if __name__ == "__main__":
    asyncio.run(main())
