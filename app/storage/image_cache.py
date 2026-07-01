import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ImageCacheEntry
from app.storage.client import ObjectStorage
from app.storage.images import MirroredImage

logger = logging.getLogger(__name__)


class ImageCache:
    def __init__(self, db: AsyncSession, storage: ObjectStorage | None = None) -> None:
        self.db = db
        self._storage = storage
        self.settings = get_settings()

    async def record_mirrored_cover(self, image: MirroredImage) -> ImageCacheEntry:
        now = datetime.now(UTC)
        values = {
            "provider": image.provider,
            "provider_item_id": image.provider_item_id,
            "source_url": image.source_url,
            "object_key": image.key,
            "public_url": image.url,
            "mime_type": image.content_type,
            "size_bytes": image.size_bytes,
            "width": image.width,
            "height": image.height,
            "content_hash": image.content_hash,
            "access_count": 1,
            "last_accessed_at": now,
            "created_at": now,
            "updated_at": now,
        }
        insert_stmt = insert(ImageCacheEntry).values(**values)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_image_cache_object_key",
            set_={
                "provider": image.provider,
                "provider_item_id": image.provider_item_id,
                "source_url": image.source_url,
                "public_url": image.url,
                "mime_type": image.content_type,
                "size_bytes": image.size_bytes,
                "width": image.width,
                "height": image.height,
                "content_hash": image.content_hash,
                "access_count": ImageCacheEntry.access_count + 1,
                "last_accessed_at": now,
                "updated_at": now,
            },
        ).returning(ImageCacheEntry)
        stmt = (
            select(ImageCacheEntry)
            .from_statement(upsert_stmt)
            .execution_options(populate_existing=True)
        )
        entry = (await self.db.scalars(stmt)).one()

        await self.db.flush()
        await self.evict_if_needed(protected_keys={image.key})
        return entry

    async def cached_provider_cover(
        self,
        *,
        provider: str,
        source_url: str,
    ) -> ImageCacheEntry | None:
        entry = await self.db.scalar(
            select(ImageCacheEntry)
            .where(
                ImageCacheEntry.provider == provider,
                ImageCacheEntry.source_url == source_url,
            )
            .order_by(ImageCacheEntry.updated_at.desc())
            .limit(1)
        )
        if entry is None:
            return None
        entry.access_count += 1
        entry.last_accessed_at = datetime.now(UTC)
        await self.db.flush()
        return entry

    async def total_size_bytes(self) -> int:
        total = await self.db.scalar(select(func.coalesce(func.sum(ImageCacheEntry.size_bytes), 0)))
        return int(total or 0)

    async def evict_if_needed(self, protected_keys: set[str] | None = None) -> int:
        max_bytes = self.settings.image_cache_max_bytes
        if max_bytes <= 0:
            return 0

        total = await self.total_size_bytes()
        if total <= max_bytes:
            return 0

        protected_keys = protected_keys or set()
        target_bytes = self.settings.image_cache_evict_target_bytes
        evicted = 0

        while total > target_bytes:
            stmt = select(ImageCacheEntry).order_by(
                ImageCacheEntry.last_accessed_at.asc(),
                ImageCacheEntry.access_count.asc(),
                ImageCacheEntry.created_at.asc(),
            )
            if protected_keys:
                stmt = stmt.where(ImageCacheEntry.object_key.notin_(protected_keys))
            result = await self.db.scalars(stmt.limit(self.settings.image_cache_cleanup_batch_size))
            candidates = list(result)
            if not candidates:
                break

            eviction_batch = []
            projected_total = total
            for entry in candidates:
                eviction_batch.append(entry)
                projected_total -= entry.size_bytes
                if projected_total <= target_bytes:
                    break

            keys = [entry.object_key for entry in eviction_batch]
            try:
                await asyncio.to_thread(self._delete_objects, keys)
            except Exception:
                logger.warning(
                    "Failed to delete cached image objects during eviction",
                    exc_info=True,
                )
                break

            for entry in eviction_batch:
                total -= entry.size_bytes
                await self.db.delete(entry)
                evicted += 1

            await self.db.flush()

        return evicted

    def _delete_objects(self, keys: list[str]) -> None:
        if self._storage is None:
            self._storage = ObjectStorage.shared()
        self._storage.delete_objects(keys)
