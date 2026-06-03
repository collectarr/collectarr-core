import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    BundleRelease,
    BundleReleaseProviderLink,
    Character,
    Item,
    ItemProviderLink,
    Person,
    Tag,
)
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
        "characters": {
            "edges": [
                {
                    "role": "MAIN",
                    "node": {
                        "name": {"full": "Monkey D. Luffy"},
                        "siteUrl": "https://anilist.co/character/40/Monkey-D-Luffy",
                        "image": {
                            "large": "https://s4.anilist.co/file/anilistcdn/character/large/40.jpg",
                            "medium": "https://s4.anilist.co/file/anilistcdn/character/medium/40.jpg",
                        },
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
        "characters": {
            "edges": [
                {
                    "role": "MAIN",
                    "node": {
                        "name": {"full": "Monkey D. Luffy"},
                        "siteUrl": "https://anilist.co/character/40/Monkey-D-Luffy",
                        "image": {
                            "large": "https://s4.anilist.co/file/anilistcdn/character/large/40.jpg",
                            "medium": "https://s4.anilist.co/file/anilistcdn/character/medium/40.jpg",
                        },
                    },
                }
            ]
        },
        "relations": {
            "edges": [
                {
                    "relationType": "PREQUEL",
                    "node": {
                        "id": 20,
                        "type": "ANIME",
                        "format": "TV",
                        "title": {
                            "romaji": "One Piece Season 1",
                            "english": "One Piece Season 1",
                            "native": "ONE PIECE Season 1",
                        },
                        "startDate": {"year": 1999},
                        "coverImage": {
                            "medium": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/20.jpg",
                        },
                    },
                },
                {
                    "relationType": "SEQUEL",
                    "node": {
                        "id": 22,
                        "type": "ANIME",
                        "format": "TV",
                        "title": {
                            "romaji": "One Piece Season 3",
                            "english": "One Piece Season 3",
                            "native": "ONE PIECE Season 3",
                        },
                        "startDate": {"year": 2001},
                        "coverImage": {
                            "medium": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/22.jpg",
                        },
                    },
                },
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
    assert results[0].kind == ItemKind.comic
    assert results[0].title == "One Piece"
    assert results[0].summary == "MANGA · RELEASING · 1997"
    assert results[0].image_url.endswith("30013.jpg")
    assert results[0].character_preview == ["Monkey D. Luffy"]


@pytest.mark.asyncio
async def test_anilist_provider_fetches_media_and_normalizes(monkeypatch):
    async def fake_graphql(self, query, variables):
        assert variables == {"id": 30013}
        return {"data": {"Media": _anilist_raw()}}

    monkeypatch.setattr(AniListProvider, "_graphql", fake_graphql)

    item = await AniListProvider().get_item("30013")
    normalized = await AniListProvider().normalize(item.raw)

    assert item.provider_item_id == "30013"
    assert normalized.kind == ItemKind.comic
    assert normalized.title == "One Piece"
    assert normalized.release_date.isoformat() == "1997-07-22"
    assert normalized.cover_image_url.endswith("30013.jpg")
    assert normalized.creators[0].name == "Eiichiro Oda"
    assert normalized.creators[0].role == "Story & Art"
    assert [credit.name for credit in normalized.characters] == ["Monkey D. Luffy"]
    assert [tag.name for tag in normalized.story_arcs] == ["Action", "Adventure"]
    assert normalized.provider_ids == {"anilist": "30013"}


@pytest.mark.asyncio
async def test_anilist_provider_emits_box_set_bundle_for_multi_volume_manga(monkeypatch):
    raw = _anilist_raw()
    raw["volumes"] = 3

    async def fake_graphql(self, query, variables):
        assert variables == {"id": 30013}
        return {"data": {"Media": raw}}

    monkeypatch.setattr(AniListProvider, "_graphql", fake_graphql)

    item = await AniListProvider().get_item("30013")
    normalized = await AniListProvider().normalize(item.raw)

    assert normalized.bundle_release is not None
    assert normalized.bundle_release.title == "One Piece Box Set"
    assert normalized.bundle_release.bundle_type == "box_set"
    assert [member.item.volume_name for member in normalized.bundle_release.members] == [
        "Volume 1",
        "Volume 2",
        "Volume 3",
    ]
    assert normalized.bundle_release.members[0].item.provider_ids == {
        "anilist": "30013#volume-1"
    }


@pytest.mark.asyncio
async def test_anilist_provider_searches_and_normalizes_anime(monkeypatch):
    async def fake_graphql(self, query, variables):
        assert "type: ANIME" in query
        assert variables in ({"search": "One Piece", "perPage": 20}, {"id": 21})
        if "Page(" in query:
            return {"data": {"Page": {"media": [_anilist_anime_raw()]}}}
        return {"data": {"Media": _anilist_anime_raw()}}

    monkeypatch.setattr(AniListProvider, "_graphql", fake_graphql)

    results = await AniListProvider().search(" One Piece ", ItemKind.movie)
    item = await AniListProvider().get_item("anime:21")
    normalized = await AniListProvider().normalize(item.raw)

    assert results[0].provider_item_id == "anime:21"
    assert results[0].kind == ItemKind.movie
    assert item.provider_item_id == "anime:21"
    assert normalized.kind == ItemKind.movie
    assert normalized.release_date.isoformat() == "1999-10-20"
    assert normalized.runtime_minutes == 24
    assert normalized.edition_format == "TV"
    assert [credit.name for credit in normalized.characters] == ["Monkey D. Luffy"]
    assert normalized.provider_ids == {"anilist": "anime:21"}


@pytest.mark.asyncio
async def test_anilist_provider_emits_season_pack_bundle_for_related_anime(monkeypatch):
    async def fake_graphql(self, query, variables):
        assert variables == {"id": 21}
        return {"data": {"Media": _anilist_anime_raw()}}

    monkeypatch.setattr(AniListProvider, "_graphql", fake_graphql)

    item = await AniListProvider().get_item("anime:21")
    normalized = await AniListProvider().normalize(item.raw)

    assert normalized.bundle_release is not None
    assert normalized.bundle_release.title == "One Piece Seasons"
    assert normalized.bundle_release.bundle_type == "season_pack"
    assert [member.item.title for member in normalized.bundle_release.members] == [
        "One Piece Season 1",
        "One Piece",
        "One Piece Season 3",
    ]
    assert normalized.bundle_release.members[0].item.provider_ids == {
        "anilist": "anime:20"
    }
    assert normalized.bundle_release.members[1].item.provider_ids == {
        "anilist": "anime:21"
    }
    assert normalized.bundle_release.members[2].item.provider_ids == {
        "anilist": "anime:22"
    }


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
    assert body["item"]["kind"] == "comic"
    assert body["item"]["title"] == "One Piece"

    async with AsyncSessionLocal() as db:
        item = await db.scalar(select(Item).where(Item.kind == ItemKind.comic))
        provider_ids = list(
            await db.scalars(
                select(ItemProviderLink.provider_item_id).where(
                    ItemProviderLink.provider == ExternalProvider.anilist
                )
            )
        )
        creator = await db.scalar(select(Person.name))
        character = await db.scalar(select(Character.name))
        tags = list(await db.scalars(select(Tag.name).order_by(Tag.name)))

    assert item is not None
    assert provider_ids == ["30013"]
    assert creator == "Eiichiro Oda"
    assert character == "Monkey D. Luffy"
    assert "Action" in tags
    assert "Adventure" in tags


@pytest.mark.asyncio
async def test_admin_ingest_upserts_anilist_anime_season_bundle(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="anilist", provider_item_id="anime:21", raw=_anilist_anime_raw())

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(AniListProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "anilist", "provider_item_id": "anime:21"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["kind"] == "movie"
    assert body["item"]["title"] == "One Piece"

    async with AsyncSessionLocal() as db:
        item_titles = list(
            await db.scalars(select(Item.title).where(Item.kind == ItemKind.movie).order_by(Item.title))
        )
        bundle = await db.scalar(select(BundleRelease).where(BundleRelease.bundle_type == "season_pack"))
        provider_ids = list(
            await db.execute(
                select(ItemProviderLink.provider_item_id)
                .where(ItemProviderLink.provider == ExternalProvider.anilist)
                .order_by(ItemProviderLink.provider_item_id)
            )
        )
        bundle_provider_ids = list(
            await db.scalars(
                select(BundleReleaseProviderLink.provider_item_id)
                .where(BundleReleaseProviderLink.provider == ExternalProvider.anilist)
                .order_by(BundleReleaseProviderLink.provider_item_id)
            )
        )

    assert item_titles == ["One Piece", "One Piece Season 1", "One Piece Season 3"]
    assert bundle is not None
    assert bundle.title == "One Piece Seasons"
    assert bundle_provider_ids == ["anime:21"]
    assert [row[0] for row in provider_ids] == ["anime:20", "anime:21", "anime:22"]
