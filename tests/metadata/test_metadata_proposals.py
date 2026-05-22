from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.models.canonical import ImageCacheEntry, MetadataProposal
from app.providers.base import ProviderSearchResult
from app.providers.comicvine import ComicVineProvider
from app.providers.gcd import GCDCoverFallback, GCDCoverImage, GCDProvider
from app.storage.images import ImageMirror, MirroredImage

from tests.admin.test_admin_ingest import comicvine_issue_raw
from tests.helpers import register_and_login


class FakeSearchCacheRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl


@pytest.mark.asyncio
async def test_provider_search_requires_login(client):
    response = await client.get("/metadata/providers/comicvine/search", params={"q": "spider"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_provider_search_returns_comicvine_results(client, monkeypatch):
    token = await register_and_login(client)

    async def fake_search(self, query, kind=None):
        assert query == "spider"
        return [ComicVineProvider()._search_result(comicvine_issue_raw())]

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)

    response = await client.get(
        "/metadata/providers/comicvine/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "spider"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["provider"] == "comicvine"
    assert body[0]["provider_item_id"] == "4000-12345"
    assert body[0]["title"] == "The Amazing Spider-Man #1 The Spider Strikes"
    assert body[0]["character_preview"] == ["Spider-Man"]
    assert body[0]["story_arc_preview"] == ["The Spider Strikes"]


@pytest.mark.asyncio
async def test_provider_search_series_inherits_credit_preview_from_issue_results(
    client, monkeypatch
):
    token = await register_and_login(client)

    async def fake_search(self, query, kind=None):
        assert query == "absolute batman"
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id="series-4050-1111",
                title="Absolute Batman",
                kind=ItemKind.comic,
                candidate_type="series",
                series_title="Absolute Batman",
            ),
            ProviderSearchResult(
                provider=self.name,
                provider_item_id="4000-1111",
                title="Absolute Batman #1",
                kind=ItemKind.comic,
                candidate_type="issue",
                series_title="Absolute Batman",
                issue_number="1",
                character_preview=["Batman"],
                story_arc_preview=["Absolute Power"],
            ),
        ]

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)

    response = await client.get(
        "/metadata/providers/comicvine/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "absolute batman", "kind": "comic"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["candidate_type"] == "series"
    assert body[0]["character_preview"] == ["Batman"]
    assert body[0]["story_arc_preview"] == ["Absolute Power"]


@pytest.mark.asyncio
async def test_default_provider_search_uses_kind_catalog_default(client, monkeypatch):
    token = await register_and_login(client)

    async def fake_search(self, query, kind=None):
        assert query == "absolute batman"
        assert kind == ItemKind.comic
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id="2663120",
                title="Absolute Batman #1",
                kind=ItemKind.comic,
                image_url=None,
                candidate_type="issue",
                series_title="Absolute Batman",
                issue_number="1",
                volume_start_year=2024,
                variant_name="Nick Dragotta Cover",
                is_variant=False,
            )
        ]

    monkeypatch.setattr(GCDProvider, "search", fake_search)

    response = await client.get(
        "/metadata/providers/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "absolute batman", "kind": "comic"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["provider"] == "gcd"
    assert body[0]["provider_item_id"] == "2663120"
    assert body[0]["candidate_type"] == "issue"
    assert body[0]["series_title"] == "Absolute Batman"
    assert body[0]["issue_number"] == "1"
    assert body[0]["volume_start_year"] == 2024
    assert body[0]["variant_name"] == "Nick Dragotta Cover"
    assert body[0]["is_variant"] is False


@pytest.mark.asyncio
async def test_default_provider_search_builds_comic_issue_query(client, monkeypatch):
    token = await register_and_login(client)

    async def fake_search(self, query, kind=None):
        assert query == "Absolute Batman #1 (2024)"
        assert kind == ItemKind.comic
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id="2663120",
                title="Absolute Batman #1",
                kind=ItemKind.comic,
                image_url=None,
                candidate_type="issue",
                series_title="Absolute Batman",
                issue_number="1",
                volume_start_year=2024,
            )
        ]

    monkeypatch.setattr(GCDProvider, "search", fake_search)

    response = await client.get(
        "/metadata/providers/search",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "kind": "comic",
            "series": "Absolute Batman",
            "issue_number": "1",
            "year": 2024,
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["provider_item_id"] == "2663120"


@pytest.mark.asyncio
async def test_provider_search_requires_query_or_structured_context(client):
    token = await register_and_login(client)

    response = await client.get(
        "/metadata/providers/comicvine/search",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "provider_query_required"


@pytest.mark.asyncio
async def test_provider_search_uses_query_cache(client, monkeypatch):
    token = await register_and_login(client)
    calls = 0

    async def fake_search(self, query, kind=None):
        nonlocal calls
        calls += 1
        return [ComicVineProvider()._search_result(comicvine_issue_raw())]

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)

    for _ in range(2):
        response = await client.get(
            "/metadata/providers/comicvine/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": "spider", "kind": "comic"},
        )
        assert response.status_code == 200
        assert response.json()[0]["provider_item_id"] == "4000-12345"

    assert calls == 1


@pytest.mark.asyncio
async def test_provider_search_uses_redis_query_cache(client, monkeypatch):
    token = await register_and_login(client)
    fake = FakeSearchCacheRedis()
    calls = 0

    @asynccontextmanager
    async def fake_redis_client():
        yield fake

    async def fake_search(self, query, kind=None):
        nonlocal calls
        calls += 1
        return [ComicVineProvider()._search_result(comicvine_issue_raw())]

    monkeypatch.setattr("app.services.provider_search_state.redis_client", fake_redis_client)
    monkeypatch.setattr(ComicVineProvider, "search", fake_search)

    for _ in range(2):
        response = await client.get(
            "/metadata/providers/comicvine/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": "spider", "kind": "comic"},
        )
        assert response.status_code == 200
        assert response.json()[0]["provider_item_id"] == "4000-12345"

    assert calls == 1
    assert fake.values
    assert next(iter(fake.ttls.values())) > 0


@pytest.mark.asyncio
async def test_provider_search_uses_cached_mirror_when_enabled_with_override(
    client, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"test@example.com"})
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")
    monkeypatch.setattr(settings, "mirror_provider_images", True)
    monkeypatch.setattr(settings, "mirror_provider_images_allow_restricted", True)
    token = await register_and_login(client)
    source_url = "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"

    async with AsyncSessionLocal() as db:
        db.add(
            ImageCacheEntry(
                provider="comicvine",
                provider_item_id="4000-12345",
                source_url=source_url,
                object_key="covers/comicvine/4000-12345/cover.webp",
                public_url="http://storage.test/covers/comicvine/4000-12345/cover.webp",
                mime_type="image/webp",
                size_bytes=1234,
                width=400,
                height=600,
                content_hash="cached-abc123",
                access_count=1,
                last_accessed_at=datetime.now(UTC),
            )
        )
        await db.commit()

    async def fake_search(self, query, kind=None):
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id="4000-12345",
                title="The Amazing Spider-Man #1",
                kind=ItemKind.comic,
                image_url=source_url,
            )
        ]

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("provider search should reuse cached mirrors only")

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    response = await client.get(
        "/metadata/providers/comicvine/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "spider", "kind": "comic"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["image_url"] == "http://storage.test/covers/comicvine/4000-12345/cover.webp"

    async with AsyncSessionLocal() as db:
        cache_entry = await db.scalar(select(ImageCacheEntry))
        assert cache_entry is not None
        assert cache_entry.provider == "comicvine"
        assert cache_entry.source_url == source_url


@pytest.mark.asyncio
async def test_provider_search_skips_uncached_cover_mirroring_on_hot_path(
    client, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"test@example.com"})
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")
    monkeypatch.setattr(settings, "mirror_provider_images", True)
    monkeypatch.setattr(settings, "mirror_provider_images_allow_restricted", True)
    token = await register_and_login(client)
    source_url = "https://comicvine.gamespot.com/a/uploads/scale_large/uncached-hot-path.jpg"

    async def fake_search(self, query, kind=None):
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id="4000-55555",
                title="The Amazing Spider-Man #2",
                kind=ItemKind.comic,
                image_url=source_url,
            )
        ]

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("provider search hot path should not mirror uncached covers")

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    response = await client.get(
        "/metadata/providers/comicvine/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "spider", "kind": "comic"},
    )

    assert response.status_code == 200
    assert response.json()[0]["image_url"] == source_url

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(ImageCacheEntry)) is None


@pytest.mark.asyncio
async def test_provider_search_keeps_restricted_cover_external_without_override(
    client, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"test@example.com"})
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")
    monkeypatch.setattr(settings, "mirror_provider_images", True)
    monkeypatch.setattr(settings, "mirror_provider_images_allow_restricted", False)
    token = await register_and_login(client)
    source_url = "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"

    async def fake_search(self, query, kind=None):
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id="4000-12345",
                title="The Amazing Spider-Man #1",
                kind=ItemKind.comic,
                image_url=source_url,
            )
        ]

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("restricted provider images should stay external")

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    response = await client.get(
        "/metadata/providers/comicvine/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "spider", "kind": "comic"},
    )

    assert response.status_code == 200
    assert response.json()[0]["image_url"] == source_url


@pytest.mark.asyncio
async def test_gcd_cover_proxy_mirrors_inline_cover_when_enabled(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mirror_provider_images", True)
    monkeypatch.setattr(settings, "mirror_provider_images_allow_restricted", True)
    source_url = "https://files1.comics.org/img/gcd/covers/cover.jpg"

    async def fake_get_cover_image(self, provider_item_id, fallback=None):
        assert provider_item_id == "3377500"
        assert fallback == GCDCoverFallback(
            series_title="Absolute Batman",
            issue_number="1",
            start_year=2024,
            variant_hint="Jim Lee",
        )
        return GCDCoverImage.inline(b"cover-bytes", "image/jpeg", source_url=source_url)

    async def fake_mirror_cover_bytes(
        self,
        image_bytes,
        *,
        source_url,
        provider,
        provider_item_id,
    ):
        assert image_bytes == b"cover-bytes"
        assert source_url == "https://files1.comics.org/img/gcd/covers/cover.jpg"
        assert provider == "gcd"
        assert provider_item_id == "3377500"
        return MirroredImage(
            key="covers/gcd/3377500/cover.webp",
            url="http://storage.test/covers/gcd/3377500/cover.webp",
            content_type="image/webp",
            source_url=source_url,
            provider=provider,
            provider_item_id=provider_item_id,
            size_bytes=1234,
            width=400,
            height=600,
            content_hash="abc123",
        )

    monkeypatch.setattr(GCDProvider, "get_cover_image", fake_get_cover_image)
    monkeypatch.setattr(ImageMirror, "mirror_cover_bytes_best_effort", fake_mirror_cover_bytes)

    response = await client.get(
        "/metadata/providers/gcd/images/3377500",
        params={
            "series": "Absolute Batman",
            "issue": "1",
            "year": 2024,
            "variant": "Jim Lee",
        },
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://storage.test/covers/gcd/3377500/cover.webp"
    assert response.headers["cache-control"] == "public, max-age=86400"

    async with AsyncSessionLocal() as db:
        cache_entry = await db.scalar(select(ImageCacheEntry))
        assert cache_entry is not None
        assert cache_entry.provider == "gcd"
        assert cache_entry.source_url == source_url


@pytest.mark.asyncio
async def test_provider_search_rejects_provider_for_wrong_kind(client):
    token = await register_and_login(client)

    response = await client.get(
        "/metadata/providers/comicvine/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "spider", "kind": "book"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Provider 'comicvine' does not support kind 'book'"


@pytest.mark.asyncio
async def test_provider_search_returns_planned_provider_stub(client):
    token = await register_and_login(client)

    response = await client.get(
        "/metadata/providers/tmdb/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "the matrix"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["provider"] == "tmdb"
    assert body[0]["provider_item_id"] == "stub-movie-the-matrix"
    assert body[0]["kind"] == "movie"


@pytest.mark.asyncio
async def test_metadata_proposal_is_saved_without_user_collection_data(client):
    token = await register_and_login(client)

    response = await client.post(
        "/metadata/proposals",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "comicvine",
            "provider_item_id": "4000-12345",
            "query": "missing spider-man issue",
            "title": "The Amazing Spider-Man #1 The Spider Strikes",
            "summary": "Candidate metadata from ComicVine.",
            "image_url": "https://example.test/cover.jpg",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["provider"] == "comicvine"

    async with AsyncSessionLocal() as db:
        proposal = await db.scalar(select(MetadataProposal))
        assert proposal is not None
        assert proposal.query == "missing spider-man issue"
        assert proposal.title == "The Amazing Spider-Man #1 The Spider Strikes"


@pytest.mark.asyncio
async def test_metadata_proposal_requires_explicit_provider(client):
    token = await register_and_login(client)

    response = await client.post(
        "/metadata/proposals",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "missing metadata",
            "title": "No provider fallback",
        },
    )

    assert response.status_code == 422
