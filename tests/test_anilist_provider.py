import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import ExternalProviderId, Item, Person, Tag
from app.providers.anilist import AniListProvider
from app.providers.base import ProviderItem
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


def _anilist_raw() -> dict:
    return {
        "id": 30013,
        "idMal": 13,
        "siteUrl": "https://anilist.co/manga/30013/One-Piece/",
        "title": {
            "romaji": "One Piece",
            "english": "One Piece",
            "native": "ONE PIECE",
        },
        "description": "A grand pirate adventure.",
        "format": "MANGA",
        "status": "RELEASING",
        "chapters": None,
        "volumes": None,
        "startDate": {"year": 1997, "month": 7, "day": 22},
        "coverImage": {
            "large": "https://s4.anilist.co/file/anilistcdn/media/manga/cover/large/30013.jpg",
            "medium": "https://s4.anilist.co/file/anilistcdn/media/manga/cover/medium/30013.jpg",
        },
        "genres": ["Action", "Adventure"],
        "staff": {
            "edges": [
                {
                    "role": "Story & Art",
                    "node": {
                        "name": {"full": "Eiichiro Oda"},
                        "siteUrl": "https://anilist.co/staff/96884/Eiichiro-Oda",
                    },
                }
            ]
        },
    }


def _anilist_anime_raw() -> dict:
    return {
        "id": 21,
        "idMal": 21,
        "siteUrl": "https://anilist.co/anime/21/One-Piece/",
        "media_type": "anime",
        "type": "ANIME",
        "title": {
            "romaji": "One Piece",
            "english": "One Piece",
            "native": "ONE PIECE",
        },
        "description": "A grand pirate adventure.",
        "format": "TV",
        "status": "RELEASING",
        "episodes": None,
        "duration": 24,
        "startDate": {"year": 1999, "month": 10, "day": 20},
        "coverImage": {
            "large": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/21.jpg",
            "medium": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/21.jpg",
        },
        "genres": ["Action", "Adventure"],
        "staff": {
            "edges": [
                {
                    "role": "Original Creator",
                    "node": {
                        "name": {"full": "Eiichiro Oda"},
                        "siteUrl": "https://anilist.co/staff/96884/Eiichiro-Oda",
                    },
                }
            ]
        },
    }


@pytest.mark.asyncio
async def test_anilist_provider_search_normalizes_results(monkeypatch):
    async def fake_graphql(self, query, variables):
        assert variables == {"search": "One Piece", "perPage": 20}
        return {"data": {"Page": {"media": [_anilist_raw()]}}}

    monkeypatch.setattr(AniListProvider, "_graphql", fake_graphql)

    results = await AniListProvider().search(" One Piece ")

    assert len(results) == 1
    assert results[0].provider_item_id == "30013"
    assert results[0].kind == ItemKind.manga
    assert results[0].title == "One Piece"
    assert results[0].summary == "MANGA · RELEASING · 1997"
    assert results[0].image_url.endswith("30013.jpg")


@pytest.mark.asyncio
async def test_anilist_provider_fetches_media_and_normalizes(monkeypatch):
    async def fake_graphql(self, query, variables):
        assert variables == {"id": 30013}
        return {"data": {"Media": _anilist_raw()}}

    monkeypatch.setattr(AniListProvider, "_graphql", fake_graphql)

    item = await AniListProvider().get_item("30013")
    normalized = await AniListProvider().normalize(item.raw)

    assert item.provider_item_id == "30013"
    assert normalized.kind == ItemKind.manga
    assert normalized.title == "One Piece"
    assert normalized.release_date.isoformat() == "1997-07-22"
    assert normalized.cover_image_url.endswith("30013.jpg")
    assert normalized.creators[0].name == "Eiichiro Oda"
    assert normalized.creators[0].role == "Story & Art"
    assert [tag.name for tag in normalized.story_arcs] == ["Action", "Adventure"]
    assert normalized.provider_ids == {"anilist": "30013"}


@pytest.mark.asyncio
async def test_anilist_provider_searches_and_normalizes_anime(monkeypatch):
    async def fake_graphql(self, query, variables):
        assert "type: ANIME" in query
        assert variables in ({"search": "One Piece", "perPage": 20}, {"id": 21})
        if "Page(" in query:
            return {"data": {"Page": {"media": [_anilist_anime_raw()]}}}
        return {"data": {"Media": _anilist_anime_raw()}}

    monkeypatch.setattr(AniListProvider, "_graphql", fake_graphql)

    results = await AniListProvider().search(" One Piece ", ItemKind.anime)
    item = await AniListProvider().get_item("anime:21")
    normalized = await AniListProvider().normalize(item.raw)

    assert results[0].provider_item_id == "anime:21"
    assert results[0].kind == ItemKind.anime
    assert item.provider_item_id == "anime:21"
    assert normalized.kind == ItemKind.anime
    assert normalized.release_date.isoformat() == "1999-10-20"
    assert normalized.runtime_minutes == 24
    assert normalized.edition_format == "TV"
    assert normalized.provider_ids == {"anilist": "anime:21"}


@pytest.mark.asyncio
async def test_admin_ingest_upserts_anilist_manga(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="anilist", provider_item_id="30013", raw=_anilist_raw())

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(AniListProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "anilist", "provider_item_id": "30013"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["kind"] == "manga"
    assert body["item"]["title"] == "One Piece"

    async with AsyncSessionLocal() as db:
        item = await db.scalar(select(Item).where(Item.kind == ItemKind.manga))
        provider_ids = list(
            await db.scalars(
                select(ExternalProviderId.provider_item_id).where(
                    ExternalProviderId.provider == ExternalProvider.anilist
                )
            )
        )
        creator = await db.scalar(select(Person.name))
        tags = list(await db.scalars(select(Tag.name).order_by(Tag.name)))

    assert item is not None
    assert provider_ids == ["30013"]
    assert creator == "Eiichiro Oda"
    assert tags == ["Action", "Adventure"]
