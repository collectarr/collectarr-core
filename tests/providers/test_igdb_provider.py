import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import Item, ItemProviderLink, Organization, Person, Tag
from app.providers.base import ProviderItem
from app.providers.igdb import IGDBProvider
from app.search.client import SearchClient


async def _admin_token(client, monkeypatch) -> str:
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})
    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _game_raw() -> dict:
    return {
        "id": 1020,
        "name": "The Legend of Zelda: Breath of the Wild",
        "summary": "Adventure across Hyrule.",
        "first_release_date": 1488499200,
        "cover": {"url": "//images.igdb.com/igdb/image/upload/t_thumb/co1r7f.jpg"},
        "genres": [{"name": "Adventure"}],
        "platforms": [{"name": "Nintendo Switch"}, {"name": "Wii U"}],
        "involved_companies": [
            {"developer": True, "publisher": False, "company": {"name": "Nintendo EPD"}},
            {"developer": False, "publisher": True, "company": {"name": "Nintendo"}},
        ],
    }


@pytest.mark.asyncio
async def test_igdb_provider_returns_stub_without_credentials():
    results = await IGDBProvider().search("Zelda")

    assert len(results) == 1
    assert results[0].provider_item_id == "stub-game-zelda"
    assert results[0].kind == ItemKind.game


@pytest.mark.asyncio
async def test_igdb_provider_search_normalizes_games(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "igdb_client_id", "client-id")
    monkeypatch.setattr(settings, "igdb_access_token", "token")

    async def fake_request(self, endpoint, body):
        assert endpoint == "games"
        assert 'search "Zelda";' in body
        return [_game_raw()]

    monkeypatch.setattr(IGDBProvider, "_request", fake_request)

    results = await IGDBProvider().search(" Zelda ")

    assert len(results) == 1
    assert results[0].provider_item_id == "1020"
    assert results[0].kind == ItemKind.game
    assert results[0].title == "The Legend of Zelda: Breath of the Wild"
    assert results[0].summary == "2017-03-03 · Nintendo Switch, Wii U"
    assert results[0].image_url == "https://images.igdb.com/igdb/image/upload/t_cover_big/co1r7f.jpg"


@pytest.mark.asyncio
async def test_igdb_provider_fetches_game_and_normalizes(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "igdb_client_id", "client-id")
    monkeypatch.setattr(settings, "igdb_access_token", "token")

    async def fake_request(self, endpoint, body):
        assert endpoint == "games"
        assert "where id = 1020;" in body
        return [_game_raw()]

    monkeypatch.setattr(IGDBProvider, "_request", fake_request)

    item = await IGDBProvider().get_item("1020")
    normalized = await IGDBProvider().normalize(item.raw)

    assert item.provider_item_id == "1020"
    assert normalized.kind == ItemKind.game
    assert normalized.title == "The Legend of Zelda: Breath of the Wild"
    assert normalized.publisher == "Nintendo"
    assert normalized.release_date.isoformat() == "2017-03-03"
    assert normalized.edition_format == "Nintendo Switch"
    assert normalized.creators[0].name == "Nintendo EPD"
    assert normalized.story_arcs[0].name == "Adventure"
    assert normalized.provider_ids == {"igdb": "1020"}
    assert normalized.platforms == ["Nintendo Switch", "Wii U"]


@pytest.mark.asyncio
async def test_admin_ingest_upserts_igdb_game(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="igdb", provider_item_id="1020", raw=_game_raw())

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(IGDBProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "igdb", "provider_item_id": "1020"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["kind"] == "game"
    assert body["item"]["title"] == "The Legend of Zelda: Breath of the Wild"
    assert body["item"]["publisher"] == "Nintendo"

    async with AsyncSessionLocal() as db:
        item = await db.scalar(select(Item).where(Item.kind == ItemKind.game))
        provider_ids = list(
            await db.scalars(
                select(ItemProviderLink.provider_item_id).where(
                    ItemProviderLink.provider == ExternalProvider.igdb
                )
            )
        )
        publisher = await db.scalar(select(Organization.name))
        developer = await db.scalar(select(Person.name))
        tag = await db.scalar(select(Tag.name))

    assert item is not None
    assert provider_ids == ["1020"]
    assert publisher == "Nintendo"
    assert developer == "Nintendo EPD"
    assert tag == "Adventure"
