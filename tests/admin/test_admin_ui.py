import pytest

from app.core.config import get_settings


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
async def test_admin_ui_is_served_without_api_token(client):
    response = await client.get("/admin/ui")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Collectarr Admin" in response.text
    assert "Personal library data stays local" in response.text
    assert "manual correction" in response.text
    assert ".badge.pending" in response.text
    assert "Approved</span>" in response.text
    assert "proposalQuickFilters" in response.text
    assert "Needs provider match" in response.text


@pytest.mark.asyncio
async def test_admin_provider_statuses_require_admin_and_report_stubs(client, monkeypatch):
    unauthorized = await client.get("/admin/providers")
    assert unauthorized.status_code == 401

    token = await admin_token(client, monkeypatch)
    response = await client.get("/admin/providers", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == 1
    providers = {item["name"]: item for item in body["providers"]}
    assert providers["comicvine"]["kind"] == "comic"
    assert providers["comicvine"]["status"] == "stub"
    assert providers["comicvine"]["supported_kinds"] == ["comic", "manga"]
    assert providers["comicvine"]["non_commercial_only"] is True
    assert providers["gcd"]["kind"] == "comic"
    assert providers["gcd"]["status"] == "live"
    assert providers["gcd"]["license_name"] == "CC BY-SA 4.0"
    assert providers["igdb"]["status"] == "stub"
    assert providers["igdb"]["supports_ingest"] is True
    assert providers["igdb"]["requires_user_key"] is True
    assert providers["igdb"]["non_commercial_only"] is True
    assert providers["tmdb"]["status"] == "stub"
    assert providers["tmdb"]["supports_ingest"] is True
    assert providers["tmdb"]["supported_kinds"] == ["movie", "tv", "anime"]
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
