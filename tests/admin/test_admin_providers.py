import pytest

from app.core.config import get_settings
from app.models.base import ItemKind
from app.providers.base import NormalizedItem, ProviderItem


async def admin_token(client, monkeypatch) -> str:
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})
    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_provider_statuses_are_public_and_report_stubs(client, monkeypatch):
    response = await client.get("/admin/providers")
    assert response.status_code == 200

    token = await admin_token(client, monkeypatch)
    response = await client.get("/admin/providers", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["cache_stats"] == {
        "search": {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "entries": 0,
            "backoffs": 0,
            "local_entries": 0,
            "redis_entries": 0,
            "local_backoffs": 0,
            "redis_backoffs": 0,
        },
        "preview": {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "entries": 0,
            "backoffs": 0,
            "local_entries": 0,
            "redis_entries": 0,
            "local_backoffs": 0,
            "redis_backoffs": 0,
        },
    }
    providers = {item["name"]: item for item in body["providers"]}
    assert providers["comicvine"]["kind"] == "comic"
    assert providers["comicvine"]["status"] == "stub"
    assert providers["comicvine"]["supported_kinds"] == ["comic", "manga"]
    assert providers["comicvine"]["non_commercial_only"] is True
    assert providers["comicvine"]["image_policy"] == "remote_image_only"
    assert providers["gcd"]["kind"] == "comic"
    assert providers["gcd"]["status"] == "live"
    assert providers["gcd"]["license_name"] == "CC BY-SA 4.0"
    assert providers["igdb"]["status"] == "stub"
    assert providers["igdb"]["supports_ingest"] is True
    assert providers["igdb"]["requires_user_key"] is True
    assert providers["igdb"]["non_commercial_only"] is True
    assert providers["tmdb"]["status"] == "stub"
    assert providers["tmdb"]["supports_ingest"] is True
    assert providers["tmdb"]["supported_kinds"] == ["movie", "tv", "anime", "collection"]
    assert providers["anilist"]["kind"] == "manga"
    assert providers["anilist"]["status"] == "live"
    assert providers["anilist"]["supports_ingest"] is True
    assert providers["anilist"]["supported_kinds"] == ["manga", "anime"]
    assert providers["openlibrary"]["kind"] == "book"
    assert providers["bgg"]["kind"] == "boardgame"
    assert providers["bgg"]["status"] == "stub"
    assert providers["bgg"]["supports_ingest"] is True
    assert providers["bgg"]["requires_user_key"] is True
    assert providers["bgg"]["non_commercial_only"] is True
    assert providers["musicbrainz"]["kind"] == "music"
    assert providers["musicbrainz"]["status"] == "live"
    assert providers["musicbrainz"]["supports_ingest"] is True
    assert providers["musicbrainz"]["image_policy"] == "mirrored_image"


@pytest.mark.asyncio
async def test_admin_provider_statuses_report_cache_activity(client, monkeypatch):
    from app.providers.comicvine import ComicVineProvider
    from app.providers.openlibrary import OpenLibraryProvider
    from tests.admin.test_admin_ingest import comicvine_issue_raw

    token = await admin_token(client, monkeypatch)

    async def fake_search(self, query, kind=None):
        return [ComicVineProvider()._search_result(comicvine_issue_raw())]

    async def fake_get_item(self, provider_item_id: str) -> ProviderItem:
        assert provider_item_id == "OL4242M"
        return ProviderItem(
            provider="openlibrary",
            provider_item_id=provider_item_id,
            raw={"id": 4242, "title": "The Silmarillion"},
        )

    async def fake_normalize(self, data) -> NormalizedItem:
        assert data["id"] == 4242
        return NormalizedItem(
            kind=ItemKind.book,
            title="The Silmarillion",
            edition_format="Hardcover",
            provider_ids={"openlibrary": "OL4242M"},
            volume_provider_ids={"openlibrary": "OL4242M"},
        )

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)
    monkeypatch.setattr(OpenLibraryProvider, "get_item", fake_get_item)
    monkeypatch.setattr(OpenLibraryProvider, "normalize", fake_normalize)

    for _ in range(2):
        response = await client.post(
            "/admin/providers/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "comicvine", "query": "spider", "kind": "comic"},
        )
        assert response.status_code == 200

    for _ in range(2):
        response = await client.post(
            "/admin/providers/preview",
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "openlibrary", "provider_item_id": "OL4242M"},
        )
        assert response.status_code == 200

    response = await client.get("/admin/providers", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["cache_stats"]["search"] == {
        "hits": 1,
        "misses": 1,
        "writes": 1,
        "entries": 1,
        "backoffs": 0,
        "local_entries": 1,
        "redis_entries": 0,
        "local_backoffs": 0,
        "redis_backoffs": 0,
    }
    assert body["cache_stats"]["preview"] == {
        "hits": 1,
        "misses": 1,
        "writes": 1,
        "entries": 1,
        "backoffs": 0,
        "local_entries": 1,
        "redis_entries": 0,
        "local_backoffs": 0,
        "redis_backoffs": 0,
    }
