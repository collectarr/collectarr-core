from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import ImageCacheEntry
from app.storage.image_cache import ImageCache
from app.storage.images import MirroredImage


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_objects(self, keys: list[str]) -> None:
        self.deleted.extend(keys)


def mirrored_image(key: str = "covers/comicvine/4000-12345/cover.webp") -> MirroredImage:
    return MirroredImage(
        key=key,
        url=f"http://storage.test/{key}",
        content_type="image/webp",
        source_url="https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg",
        provider="comicvine",
        provider_item_id="4000-12345",
        size_bytes=12345,
        width=823,
        height=1280,
        content_hash="abc123",
    )


def mirrored_image_for_source(
    *,
    key: str,
    source_url: str,
    provider_item_id: str,
    content_hash: str = "abc123",
) -> MirroredImage:
    return MirroredImage(
        key=key,
        url=f"http://storage.test/{key}",
        content_type="image/webp",
        source_url=source_url,
        provider="comicvine",
        provider_item_id=provider_item_id,
        size_bytes=12345,
        width=823,
        height=1280,
        content_hash=content_hash,
    )


def cache_entry(key: str, size_bytes: int, last_accessed_at: datetime) -> ImageCacheEntry:
    return ImageCacheEntry(
        provider="comicvine",
        provider_item_id="4000-12345",
        source_url=f"https://example.test/{key}.jpg",
        object_key=key,
        public_url=f"http://storage.test/{key}",
        mime_type="image/webp",
        size_bytes=size_bytes,
        width=400,
        height=600,
        content_hash=f"hash-{key}",
        access_count=1,
        last_accessed_at=last_accessed_at,
    )


@pytest.mark.asyncio
async def test_image_cache_records_and_touches_mirrored_cover():
    storage = FakeStorage()
    async with AsyncSessionLocal() as db:
        cache = ImageCache(db, storage=storage)
        first = await cache.record_mirrored_cover(mirrored_image())
        second = await cache.record_mirrored_cover(
            mirrored_image(key="covers/comicvine/4000-12345/cover.webp")
        )
        await db.commit()

        assert second.id == first.id
        assert second.object_key == "covers/comicvine/4000-12345/cover.webp"
        assert second.provider == "comicvine"
        assert second.provider_item_id == "4000-12345"
        assert second.mime_type == "image/webp"
        assert second.size_bytes == 12345
        assert second.width == 823
        assert second.height == 1280
        assert second.content_hash == "abc123"
        assert second.access_count == 2
        assert storage.deleted == []


@pytest.mark.asyncio
async def test_image_cache_touches_cached_provider_cover():
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        db.add(cache_entry("cached", 30, now - timedelta(days=1)))
        await db.commit()

        cache = ImageCache(db)
        entry = await cache.cached_provider_cover(
            provider="comicvine",
            source_url="https://example.test/cached.jpg",
        )
        await db.commit()

        assert entry is not None
        assert entry.public_url == "http://storage.test/cached"
        assert entry.access_count == 2
        assert entry.last_accessed_at > now


@pytest.mark.asyncio
async def test_image_cache_keeps_distinct_provider_sources_with_same_content_hash():
    async with AsyncSessionLocal() as db:
        cache = ImageCache(db)
        first = await cache.record_mirrored_cover(
            mirrored_image_for_source(
                key="covers/comicvine/4000-12345/first.webp",
                source_url="https://example.test/first.jpg",
                provider_item_id="4000-12345",
            )
        )
        second = await cache.record_mirrored_cover(
            mirrored_image_for_source(
                key="covers/comicvine/4000-67890/second.webp",
                source_url="https://example.test/second.jpg",
                provider_item_id="4000-67890",
            )
        )
        await db.commit()

        rows = list(
            await db.scalars(
                select(ImageCacheEntry).order_by(ImageCacheEntry.object_key.asc())
            )
        )

        assert first.id != second.id
        assert [row.object_key for row in rows] == [
            "covers/comicvine/4000-12345/first.webp",
            "covers/comicvine/4000-67890/second.webp",
        ]
        assert [row.source_url for row in rows] == [
            "https://example.test/first.jpg",
            "https://example.test/second.jpg",
        ]


@pytest.mark.asyncio
async def test_image_cache_evicts_oldest_entries_until_target(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "image_cache_max_bytes", 100)
    monkeypatch.setattr(settings, "image_cache_evict_target_bytes", 80)
    monkeypatch.setattr(settings, "image_cache_cleanup_batch_size", 10)
    now = datetime.now(UTC)
    storage = FakeStorage()

    async with AsyncSessionLocal() as db:
        db.add_all(
            [
                cache_entry("old", 30, now - timedelta(days=3)),
                cache_entry("middle", 40, now - timedelta(days=2)),
                cache_entry("protected", 50, now - timedelta(days=4)),
            ]
        )
        await db.flush()

        evicted = await ImageCache(db, storage=storage).evict_if_needed(
            protected_keys={"protected"}
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        remaining = list(await db.scalars(select(ImageCacheEntry.object_key)))

    assert evicted == 2
    assert storage.deleted == ["old", "middle"]
    assert remaining == ["protected"]
