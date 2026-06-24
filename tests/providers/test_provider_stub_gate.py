import pytest

from app.core.config import get_settings
from app.models.base import ItemKind
from app.providers.bgg import BGGProvider
from app.providers.comicvine import ComicVineProvider
from app.providers.igdb import IGDBProvider
from app.providers.tmdb import TMDbProvider

UNCONFIGURED_PROVIDERS = [
    (TMDbProvider, "The Matrix", None),
    (IGDBProvider, "Zelda", None),
    (BGGProvider, "Catan", ItemKind.boardgame),
    (ComicVineProvider, "Batman", ItemKind.comic),
]


@pytest.fixture
def production_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "prod-secret-value")
    monkeypatch.delenv("DEV_STUB_PROVIDERS", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_cls, query, kind", UNCONFIGURED_PROVIDERS)
async def test_unconfigured_provider_returns_no_stub_in_production(
    production_env, provider_cls, query, kind
):
    results = await provider_cls().search(query, kind)
    assert results == []


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_cls, query, kind", UNCONFIGURED_PROVIDERS)
async def test_dev_stub_flag_enables_stub_in_production(
    monkeypatch, provider_cls, query, kind
):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "prod-secret-value")
    monkeypatch.setenv("DEV_STUB_PROVIDERS", "true")
    get_settings.cache_clear()
    try:
        results = await provider_cls().search(query, kind)
        assert len(results) == 1
        assert results[0].provider_item_id.startswith("stub-")
    finally:
        get_settings.cache_clear()
