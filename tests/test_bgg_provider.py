from xml.etree import ElementTree

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import ExternalProviderId, Item, Organization, Person, Tag
from app.providers.base import ProviderItem
from app.providers.bgg import BGGProvider
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


def _bgg_raw() -> dict:
    return {
        "id": "13",
        "type": "boardgame",
        "names": [
            {"type": "primary", "sortindex": "1", "value": "CATAN"},
            {"type": "alternate", "sortindex": "1", "value": "Settlers of Catan"},
        ],
        "description": "Trade, build, and settle.",
        "yearpublished": "1995",
        "minplayers": "3",
        "maxplayers": "4",
        "playingtime": "120",
        "image": "https://cf.geekdo-images.com/catan.jpg",
        "thumbnail": "https://cf.geekdo-images.com/catan-thumb.jpg",
        "links": [
            {"type": "boardgamedesigner", "id": "7", "value": "Klaus Teuber"},
            {"type": "boardgamepublisher", "id": "37", "value": "KOSMOS"},
            {"type": "boardgamecategory", "id": "1026", "value": "Negotiation"},
            {"type": "boardgamefamily", "id": "39185", "value": "Catan"},
        ],
    }


@pytest.mark.asyncio
async def test_bgg_provider_search_normalizes_xml_results(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "bgg_api_token", "token")

    async def fake_request_xml(self, path, params):
        assert path == "search"
        assert params == {"query": "Catan", "type": "boardgame"}
        return ElementTree.fromstring(
            """
            <items total="1">
              <item type="boardgame" id="13">
                <name type="primary" value="CATAN" />
                <yearpublished value="1995" />
              </item>
            </items>
            """
        )

    monkeypatch.setattr(BGGProvider, "_request_xml", fake_request_xml)

    results = await BGGProvider().search(" Catan ")

    assert len(results) == 1
    assert results[0].provider_item_id == "13"
    assert results[0].kind == ItemKind.boardgame
    assert results[0].title == "CATAN"
    assert results[0].summary == "1995"


@pytest.mark.asyncio
async def test_bgg_provider_fetches_thing_and_normalizes(monkeypatch):
    async def fake_request_xml(self, path, params):
        assert path == "thing"
        assert params == {"id": "13", "type": "boardgame", "stats": "1"}
        return ElementTree.fromstring(
            """
            <items>
              <item type="boardgame" id="13">
                <thumbnail>https://cf.geekdo-images.com/catan-thumb.jpg</thumbnail>
                <image>https://cf.geekdo-images.com/catan.jpg</image>
                <name type="primary" sortindex="1" value="CATAN" />
                <description>Trade, build, and settle.</description>
                <yearpublished value="1995" />
                <minplayers value="3" />
                <maxplayers value="4" />
                <playingtime value="120" />
                <link type="boardgamedesigner" id="7" value="Klaus Teuber" />
                <link type="boardgamepublisher" id="37" value="KOSMOS" />
                <link type="boardgamecategory" id="1026" value="Negotiation" />
                <link type="boardgamefamily" id="39185" value="Catan" />
              </item>
            </items>
            """
        )

    monkeypatch.setattr(BGGProvider, "_request_xml", fake_request_xml)

    item = await BGGProvider().get_item("13")
    normalized = await BGGProvider().normalize(item.raw)

    assert item.provider_item_id == "13"
    assert normalized.kind == ItemKind.boardgame
    assert normalized.title == "CATAN"
    assert normalized.publisher == "KOSMOS"
    assert normalized.release_date.year == 1995
    assert normalized.cover_image_url == "https://cf.geekdo-images.com/catan.jpg"
    assert normalized.creators[0].name == "Klaus Teuber"
    assert normalized.characters[0].name == "Negotiation"
    assert normalized.story_arcs[0].name == "Catan"
    assert normalized.provider_ids == {"bgg": "13"}


@pytest.mark.asyncio
async def test_admin_ingest_upserts_bgg_boardgame(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="bgg", provider_item_id="13", raw=_bgg_raw())

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(BGGProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "bgg", "provider_item_id": "13"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["kind"] == "boardgame"
    assert body["item"]["title"] == "CATAN"
    assert body["item"]["publisher"] == "KOSMOS"

    async with AsyncSessionLocal() as db:
        item = await db.scalar(select(Item).where(Item.kind == ItemKind.boardgame))
        provider_ids = list(
            await db.scalars(
                select(ExternalProviderId.provider_item_id).where(
                    ExternalProviderId.provider == ExternalProvider.bgg
                )
            )
        )
        publisher = await db.scalar(select(Organization.name))
        designer = await db.scalar(select(Person.name))
        tags = list(await db.scalars(select(Tag.name).order_by(Tag.name)))

    assert item is not None
    assert provider_ids == ["13"]
    assert publisher == "KOSMOS"
    assert designer == "Klaus Teuber"
    assert tags == ["Catan", "Negotiation"]
