import pytest

from app.core.config import get_settings
from app.providers.comicvine import ComicVineProvider


@pytest.mark.asyncio
async def test_find_issue_cover_matches_exact_volume_year_and_issue(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")
    requests = []

    async def fake_request(self, path, params):
        requests.append((path, params))
        if path == "search/":
            return {
                "results": [
                    {"id": 111, "name": "Absolute Batman", "start_year": "2025"},
                    {"id": 160294, "name": "Absolute Batman", "start_year": "2024"},
                ]
            }
        if path == "issues/":
            assert params["filter"] == "volume:160294,issue_number:1"
            return {
                "results": [
                    {
                        "id": 1073108,
                        "api_detail_url": (
                            "https://comicvine.gamespot.com/api/issue/4000-1073108/"
                        ),
                        "site_detail_url": (
                            "https://comicvine.gamespot.com/absolute-batman-1/4000-1073108/"
                        ),
                        "issue_number": "1",
                        "image": {
                            "super_url": (
                                "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
                            )
                        },
                    }
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(ComicVineProvider, "_request", fake_request)

    cover = await ComicVineProvider().find_issue_cover(
        series_title="Absolute Batman",
        issue_number="1",
        start_year=2024,
    )

    assert cover is not None
    assert cover.provider_item_id == "4000-1073108"
    assert cover.image_url == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
    assert cover.site_detail_url == "https://comicvine.gamespot.com/absolute-batman-1/4000-1073108/"
    assert requests[0][0] == "search/"
    assert requests[1][0] == "issues/"


@pytest.mark.asyncio
async def test_find_issue_cover_returns_none_without_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", None)

    async def fail_request(self, path, params):
        raise AssertionError("Unconfigured provider should not call ComicVine")

    monkeypatch.setattr(ComicVineProvider, "_request", fail_request)

    assert (
        await ComicVineProvider().find_issue_cover(
            series_title="Absolute Batman",
            issue_number="1",
            start_year=2024,
        )
        is None
    )
