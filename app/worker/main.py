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

from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import ImageAsset
from app.search.client import SearchClient
from app.storage.client import ObjectStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CatalogFingerprint:
    item_count: int
    item_updated_at: datetime | None
    contained_value_count: int
    contained_value_updated_at: datetime | None


def _compute_phash(image_data: bytes) -> str:
    with Image.open(BytesIO(image_data)) as pil_image:
        return str(imagehash.phash(pil_image))


async def catalog_fingerprint(db: AsyncSession) -> CatalogFingerprint:
    item_count = 0
    item_updated_at: datetime | None = None
    contained_value_count = 0
    contained_value_updated_at: datetime | None = None

    for definition in CATALOG_KIND_DEFINITIONS:
        table = definition.model
        count = await db.scalar(select(func.count()).select_from(table))
        updated_at = await db.scalar(select(func.max(table.updated_at)))
        item_count += count or 0
        if updated_at and (item_updated_at is None or updated_at > item_updated_at):
            item_updated_at = updated_at

    for definition in CATALOG_KIND_DEFINITIONS:
        if not definition.contained_count_fields:
            continue
        model = definition.model
        fields = definition.contained_count_fields
        details = getattr(model, "details", None)
        lengths = [
            func.coalesce(
                func.jsonb_array_length(
                    details[field] if details is not None else getattr(model, field)
                ),
                0,
            )
            for field in fields
        ]
        count = await db.scalar(select(func.coalesce(func.sum(sum(lengths)), 0)).select_from(model))
        updated_at = await db.scalar(select(func.max(model.updated_at)))
        contained_value_count += count or 0
        if updated_at and (
            contained_value_updated_at is None or updated_at > contained_value_updated_at
        ):
            contained_value_updated_at = updated_at

    return CatalogFingerprint(
        item_count=item_count,
        item_updated_at=item_updated_at,
        contained_value_count=contained_value_count,
        contained_value_updated_at=contained_value_updated_at,
    )


async def index_once(search: SearchClient) -> None:
    async with AsyncSessionLocal() as db:
        documents = []
        for definition in CATALOG_KIND_DEFINITIONS:
            rows = await db.execute(select(definition.model))
            documents.extend(definition.search_document(item) for item in rows.scalars().unique())
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
            "worker_index_failed items=%s contained_values=%s error=%s",
            current_fingerprint.item_count,
            current_fingerprint.contained_value_count,
            exc,
        )
        return last_fingerprint

    logger.info(
        "worker_index_finished items=%s contained_values=%s",
        current_fingerprint.item_count,
        current_fingerprint.contained_value_count,
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
                    body, _ = await asyncio.to_thread(storage.get_object, asset.storage_key)
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
