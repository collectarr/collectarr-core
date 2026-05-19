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
    assert requests[-1][0] == "issues/"
    assert sum(1 for path, _ in requests if path == "search/") >= 1


@pytest.mark.asyncio
async def test_find_issue_cover_prefers_variant_hint(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")

    async def fake_request(self, path, params):
        if path == "search/":
            return {"results": [{"id": 160294, "name": "Absolute Batman", "start_year": "2024"}]}
        if path == "issues/":
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
                        "name": "Standard Cover",
                        "issue_number": "1",
                        "image": {
                            "super_url": (
                                "https://comicvine.gamespot.com/a/uploads/scale_large/standard.jpg"
                            )
                        },
                    },
                    {
                        "id": 1073109,
                        "api_detail_url": (
                            "https://comicvine.gamespot.com/api/issue/4000-1073109/"
                        ),
                        "site_detail_url": (
                            "https://comicvine.gamespot.com/absolute-batman-1-jim-lee/4000-1073109/"
                        ),
                        "name": "Jim Lee & Scott Williams Variant Cover",
                        "issue_number": "1",
                        "deck": "Cardstock variant cover.",
                        "image": {
                            "super_url": (
                                "https://comicvine.gamespot.com/a/uploads/scale_large/jim-lee.jpg"
                            )
                        },
                    },
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(ComicVineProvider, "_request", fake_request)

    cover = await ComicVineProvider().find_issue_cover(
        series_title="Absolute Batman",
        issue_number="1",
        start_year=2024,
        variant_hint="Jim Lee & Scott Williams Cardstock Variant Cover",
    )

    assert cover is not None
    assert cover.provider_item_id == "4000-1073109"
    assert cover.image_url == "https://comicvine.gamespot.com/a/uploads/scale_large/jim-lee.jpg"


@pytest.mark.asyncio
async def test_find_issue_cover_requires_variant_match_when_requested(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")

    async def fake_request(self, path, params):
        if path == "search/":
            return {"results": [{"id": 160294, "name": "Absolute Batman", "start_year": "2024"}]}
        if path == "issues/":
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
                        "name": "The Zoo, Part One",
                        "issue_number": "1",
                        "deck": "Scott Snyder and Nick Dragotta launch Absolute Batman.",
                        "image": {
                            "super_url": (
                                "https://comicvine.gamespot.com/a/uploads/scale_large/standard.jpg"
                            )
                        },
                    },
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(ComicVineProvider, "_request", fake_request)

    cover = await ComicVineProvider().find_issue_cover(
        series_title="Absolute Batman",
        issue_number="1",
        start_year=2024,
        variant_hint="Jim Lee & Scott Williams Cardstock Variant Cover",
        require_variant_match=True,
    )

    assert cover is None


@pytest.mark.asyncio
async def test_find_issue_cover_rejects_standard_cover_for_distinctive_variant(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")

    async def fake_request(self, path, params):
        if path == "search/":
            return {"results": [{"id": 160294, "name": "Absolute Batman", "start_year": "2024"}]}
        if path == "issues/":
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
                        "name": "Nick Dragotta Cover",
                        "issue_number": "1",
                        "deck": "Scott Snyder and Nick Dragotta launch Absolute Batman.",
                        "image": {
                            "super_url": (
                                "https://comicvine.gamespot.com/a/uploads/scale_large/standard.jpg"
                            )
                        },
                    },
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(ComicVineProvider, "_request", fake_request)

    cover = await ComicVineProvider().find_issue_cover(
        series_title="Absolute Batman",
        issue_number="1",
        start_year=2024,
        variant_hint="Nick Dragotta Foil Cardstock Variant Cover",
        require_variant_match=True,
    )

    assert cover is None


@pytest.mark.asyncio
async def test_provider_normalizes_associated_images_as_variant_covers():
    normalized = await ComicVineProvider().normalize(
        {
            "id": 498453,
            "api_detail_url": "https://comicvine.gamespot.com/api/issue/4000-498453/",
            "site_detail_url": (
                "https://comicvine.gamespot.com/over-the-garden-wall-1/4000-498453/"
            ),
            "name": "",
            "issue_number": "1",
            "image": {
                "super_url": "https://comicvine.gamespot.com/a/uploads/scale_large/main.jpg",
                "original_url": "https://comicvine.gamespot.com/a/uploads/original/main.jpg",
            },
            "associated_images": [
                {
                    "id": 4767296,
                    "original_url": (
                        "https://comicvine.gamespot.com/a/uploads/original/6/67663/4767296-01b.jpg"
                    ),
                    "caption": None,
                    "image_tags": "All Images",
                },
                {
                    "id": 4767295,
                    "original_url": (
                        "https://comicvine.gamespot.com/a/uploads/original/6/67663/4767295-01-sub.jpg"
                    ),
                    "caption": "Subscription cover",
                    "image_tags": "All Images",
                },
                {
                    "id": 4767000,
                    "original_url": "https://comicvine.gamespot.com/a/uploads/original/main.jpg",
                    "caption": "Duplicate primary",
                    "image_tags": "All Images",
                },
            ],
            "volume": {"id": 100090, "name": "Over The Garden Wall"},
        }
    )

    assert len(normalized.variant_covers) == 2
    assert normalized.variant_covers[0].name == "Variant cover 1"
    assert normalized.variant_covers[0].source_id == "4767296"
    assert (
        normalized.variant_covers[0].cover_image_url
        == "https://comicvine.gamespot.com/a/uploads/original/6/67663/4767296-01b.jpg"
    )
    assert normalized.variant_covers[1].name == "Subscription cover"


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
