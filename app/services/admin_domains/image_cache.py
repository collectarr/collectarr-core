from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ImageCacheEntry
from app.schemas.admin import ImageCachePurgeResponse, ImageCacheStatsResponse
from app.storage.client import ObjectStorage


class AdminImageCacheService:
    def __init__(
        self,
        db: AsyncSession,
        audit_recorder: Callable[..., None],
        logger: Any,
    ) -> None:
        self.db = db
        self._audit_recorder = audit_recorder
        self._logger = logger

    async def image_cache_stats(self) -> ImageCacheStatsResponse:
        settings = get_settings()
        total_entries = (
            await self.db.scalar(select(func.count()).select_from(ImageCacheEntry))
        ) or 0
        total_size = (
            await self.db.scalar(select(func.coalesce(func.sum(ImageCacheEntry.size_bytes), 0)))
        ) or 0
        max_bytes = settings.image_cache_max_bytes
        usage_pct = (total_size / max_bytes * 100) if max_bytes > 0 else 0.0

        rows = await self.db.execute(
            select(ImageCacheEntry.provider, func.count()).group_by(ImageCacheEntry.provider)
        )
        providers = {row[0]: row[1] for row in rows}

        return ImageCacheStatsResponse(
            total_entries=int(total_entries),
            total_size_bytes=int(total_size),
            max_size_bytes=max_bytes,
            usage_percent=round(usage_pct, 1),
            mirroring_enabled=settings.mirror_provider_images,
            providers=providers,
        )

    async def purge_image_cache(
        self,
        provider: str | None = None,
    ) -> ImageCachePurgeResponse:
        query = select(ImageCacheEntry)
        if provider:
            query = query.where(ImageCacheEntry.provider == provider)
        entries = list((await self.db.scalars(query)).all())
        if not entries:
            return ImageCachePurgeResponse(deleted_entries=0, freed_bytes=0)

        keys = [entry.object_key for entry in entries]
        freed = sum(entry.size_bytes for entry in entries)
        try:
            storage = ObjectStorage.shared()
            storage.delete_objects(keys)
        except Exception:
            self._logger.warning(
                "Failed to delete objects from storage during purge",
                exc_info=True,
            )

        delete_statement = delete(ImageCacheEntry)
        if provider:
            delete_statement = delete_statement.where(ImageCacheEntry.provider == provider)
        await self.db.execute(delete_statement)

        self._audit_recorder(
            "purge_image_cache",
            "image_cache",
            details={"provider": provider, "deleted": len(entries), "freed_bytes": freed},
        )
        await self.db.commit()
        return ImageCachePurgeResponse(deleted_entries=len(entries), freed_bytes=freed)