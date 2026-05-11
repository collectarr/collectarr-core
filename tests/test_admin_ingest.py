from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.canonical import ExternalProviderId, Item, Release, Series, Variant, Volume
from app.providers.base import ProviderItem
from app.providers.comicvine import ComicVineProvider
from app.search.client import SearchClient
from app.storage.images import MirroredImage, ImageMirror


async def admin_token(client, monkeypatch) -> str:
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})
    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def comicvine_issue_raw() -> dict:
    return {
        "id": 12345,
        "api_detail_url": "https://comicvine.gamespot.com/api/issue/4000-12345/",
        "site_detail_url": "https://comicvine.gamespot.com/amazing-spider-man-1/4000-12345/",
        "name": "The Spider Strikes",
        "issue_number": "1",
        "deck": "Peter Parker begins a new chapter.",
        "description": "<p>Peter Parker faces a new chapter as Spider-Man.</p>",
        "cover_date": "1963-03-01",
        "image": {"super_url": "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"},
        "volume": {
            "id": 6789,
            "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-6789/",
            "name": "The Amazing Spider-Man",
            "publisher": {"name": "Marvel"},
        },
    }


@pytest.mark.asyncio
async def test_comicvine_provider_normalizes_issue_payload():
    normalized = await ComicVineProvider().normalize(comicvine_issue_raw())

    assert normalized.title == "The Amazing Spider-Man"
    assert normalized.item_number == "1"
    assert normalized.edition_title == "The Spider Strikes"
    assert normalized.publisher == "Marvel"
    assert normalized.release_date == date(1963, 3, 1)
    assert normalized.provider_ids == {"comicvine": "4000-12345"}
    assert normalized.volume_provider_ids == {"comicvine": "4050-6789"}
    assert (
        normalized.cover_image_url
        == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
    )
    assert normalized.synopsis == "Peter Parker faces a new chapter as Spider-Man."


@pytest.mark.asyncio
async def test_comicvine_provider_stub_search_uses_stable_slug(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", None)

    results = await ComicVineProvider().search("  Spider-Man: Vol. 2  ")

    assert len(results) == 1
    assert results[0].provider_item_id == "stub-comic-spider-man-vol-2"
    assert results[0].title == "Spider-Man: Vol. 2 (ComicVine stub)"


@pytest.mark.asyncio
async def test_admin_provider_search_uses_provider_results(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async def fake_search(self, query):
        return [ComicVineProvider()._search_result(comicvine_issue_raw())]

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)

    response = await client.post(
        "/admin/providers/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "query": "spider"},
    )

    assert response.status_code == 200
    assert response.json()[0]["provider_item_id"] == "4000-12345"
    assert response.json()[0]["title"] == "The Amazing Spider-Man #1 The Spider Strikes"


@pytest.mark.asyncio
async def test_admin_ingest_upserts_comicvine_issue(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    indexed_documents = []

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(
            provider="comicvine", provider_item_id="4000-12345", raw=comicvine_issue_raw()
        )

    async def fake_index_documents(self, documents):
        indexed_documents.extend(documents)
        return True

    async def fake_mirror_cover(self, source_url, provider, provider_item_id):
        assert source_url == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
        assert provider == "comicvine"
        assert provider_item_id == "4000-12345"
        return MirroredImage(
            key="covers/comicvine/4000-12345/cover.jpg",
            url="http://localhost:9000/collectarr-images/covers/comicvine/4000-12345/cover.jpg",
            content_type="image/jpeg",
            thumbnail_key="thumbnails/comicvine/4000-12345/cover.jpg",
            thumbnail_url=(
                "http://localhost:9000/collectarr-images/thumbnails/comicvine/4000-12345/cover.jpg"
            ),
        )

    monkeypatch.setattr(ComicVineProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fake_mirror_cover)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "provider_item_id": "12345"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["title"] == "The Amazing Spider-Man"
    assert body["item"]["item_number"] == "1"
    assert body["item"]["editions"][0]["publisher"] == "Marvel"
    assert (
        body["item"]["editions"][0]["variants"][0]["cover_image_url"]
        == "http://localhost:9000/collectarr-images/covers/comicvine/4000-12345/cover.jpg"
    )
    assert (
        body["item"]["editions"][0]["variants"][0]["thumbnail_image_url"]
        == "http://localhost:9000/collectarr-images/thumbnails/comicvine/4000-12345/cover.jpg"
    )
    assert indexed_documents == [
        {
            "id": body["item_id"],
            "kind": "comic",
            "title": "The Amazing Spider-Man",
            "item_number": "1",
            "synopsis": "Peter Parker faces a new chapter as Spider-Man.",
            "cover_image_url": "http://localhost:9000/collectarr-images/covers/comicvine/4000-12345/cover.jpg",
            "thumbnail_image_url": (
                "http://localhost:9000/collectarr-images/thumbnails/comicvine/4000-12345/cover.jpg"
            ),
            "publisher": "Marvel",
            "region": "US",
            "release_year": 1963,
            "barcodes": [],
            "series_title": "The Amazing Spider-Man",
            "volume_name": "The Amazing Spider-Man",
        }
    ]

    second_response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "provider_item_id": "4000-12345"},
    )
    assert second_response.status_code == 201
    assert second_response.json()["created"] is False
    assert second_response.json()["item_id"] == body["item_id"]

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Item)) == 1
        assert await db.scalar(select(func.count()).select_from(Series)) == 1
        assert await db.scalar(select(func.count()).select_from(Volume)) == 1
        assert await db.scalar(select(func.count()).select_from(Variant)) == 1
        assert await db.scalar(select(func.count()).select_from(Release)) == 1
        provider_ids = await db.scalars(
            select(ExternalProviderId.provider_item_id).order_by(
                ExternalProviderId.provider_item_id
            )
        )
        assert list(provider_ids) == ["4000-12345", "4050-6789"]
        cover = await db.scalar(select(Variant.cover_image_key))
        assert cover == "covers/comicvine/4000-12345/cover.jpg"
        thumbnail = await db.scalar(select(Variant.thumbnail_image_key))
        assert thumbnail == "thumbnails/comicvine/4000-12345/cover.jpg"
