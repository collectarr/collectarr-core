import asyncio
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import logging
from time import monotonic

import imagehash
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.canonical import Edition, ImageAsset, Item, Variant, Volume
from app.schemas.admin import ProviderIngestJobRunResponse
from app.search.client import SearchClient
from app.search.documents import item_search_document
from app.services.admin import AdminMetadataService
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
    item_count, item_updated_at = (
        await db.execute(select(func.count(Item.id), func.max(Item.updated_at)))
    ).one()
    edition_count, edition_updated_at = (
        await db.execute(select(func.count(Edition.id), func.max(Edition.updated_at)))
    ).one()
    variant_count, variant_updated_at = (
        await db.execute(select(func.count(Variant.id), func.max(Variant.updated_at)))
    ).one()
    return CatalogFingerprint(
        item_count=int(item_count),
        item_updated_at=item_updated_at,
        edition_count=int(edition_count),
        edition_updated_at=edition_updated_at,
        variant_count=int(variant_count),
        variant_updated_at=variant_updated_at,
    )


async def index_once(search: SearchClient | None = None) -> None:
    search = search or SearchClient()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Item).options(
                selectinload(Item.volume).selectinload(Volume.series),
                selectinload(Item.primary_bundle_releases),
                selectinload(Item.editions).selectinload(Edition.variants),
            )
        )
        documents = [item_search_document(item) for item in result.scalars().unique()]
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


async def run_pending_provider_ingest_jobs(limit: int) -> ProviderIngestJobRunResponse:
    async with AsyncSessionLocal() as db:
        return await AdminMetadataService(db).run_pending_ingest_jobs(limit)


async def run_pending_provider_ingest_jobs_best_effort(
    limit: int,
) -> ProviderIngestJobRunResponse | None:
    try:
        result = await run_pending_provider_ingest_jobs(limit)
    except Exception as exc:
        logger.exception("worker_provider_ingest_failed limit=%s error=%s", limit, exc)
        return None

    if result.processed or result.recovered:
        logger.info(
            "worker_provider_ingest_finished processed=%s recovered=%s",
            result.processed,
            result.recovered,
        )
    return result


async def refresh_stale_catalog_items(limit: int) -> int:
    try:
        async with AsyncSessionLocal() as db:
            refreshed = await AdminMetadataService(db).refresh_stale_items(limit)
    except Exception as exc:
        logger.exception("worker_catalog_refresh_failed limit=%s error=%s", limit, exc)
        return 0

    if refreshed:
        logger.info("worker_catalog_refresh_finished refreshed=%s", refreshed)
    return refreshed


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
        "worker_starting index_interval_seconds=%s provider_ingest_interval_seconds=%s "
        "provider_ingest_batch_size=%s catalog_refresh_interval_seconds=%s "
        "catalog_refresh_stale_days=%s catalog_refresh_batch_size=%s",
        settings.worker_index_interval_seconds,
        settings.worker_provider_ingest_interval_seconds,
        settings.worker_provider_ingest_batch_size,
        settings.worker_catalog_refresh_interval_seconds,
        settings.worker_catalog_refresh_stale_days,
        settings.worker_catalog_refresh_batch_size,
    )
    await search.configure()
    ObjectStorage().ensure_bucket()
    last_fingerprint: CatalogFingerprint | None = None
    next_index_run_at = 0.0
    next_ingest_run_at = 0.0
    next_refresh_run_at = 0.0
    next_phash_run_at = 0.0

    while True:
        now = monotonic()
        if now >= next_index_run_at:
            last_fingerprint = await index_changed_catalog(search, last_fingerprint)
            next_index_run_at = monotonic() + settings.worker_index_interval_seconds

        now = monotonic()
        if now >= next_ingest_run_at:
            await run_pending_provider_ingest_jobs_best_effort(
                settings.worker_provider_ingest_batch_size
            )
            next_ingest_run_at = monotonic() + settings.worker_provider_ingest_interval_seconds

        now = monotonic()
        if now >= next_refresh_run_at:
            await refresh_stale_catalog_items(settings.worker_catalog_refresh_batch_size)
            next_refresh_run_at = monotonic() + settings.worker_catalog_refresh_interval_seconds

        now = monotonic()
        if now >= next_phash_run_at:
            await backfill_cover_phashes(limit=50)
            next_phash_run_at = monotonic() + settings.worker_index_interval_seconds

        sleep_until = min(next_index_run_at, next_ingest_run_at, next_refresh_run_at, next_phash_run_at)
        await asyncio.sleep(max(1.0, sleep_until - monotonic()))


if __name__ == "__main__":
    asyncio.run(main())
