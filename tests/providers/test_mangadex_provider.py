import pytest

from app.core.config import get_settings
from app.models.base import ItemKind
from app.providers.mangadex import MangaDexProvider


def _manga_search_response() -> dict:
    return {
        "result": "ok",
        "data": [
            {
                "id": "a1c7c817-4e59-43b7-9365-09675a149a6f",
                "type": "manga",
                "attributes": {
                    "title": {"en": "One Piece"},
                    "description": {"en": "A pirate adventure."},
                    "status": "ongoing",
                    "year": 1997,
                    "publicationDemographic": "shounen",
                    "tags": [
                        {"attributes": {"name": {"en": "Action"}}},
                        {"attributes": {"name": {"en": "Adventure"}}},
                    ],
                },
                "relationships": [
                    {
                        "type": "author",
                        "attributes": {"name": "Eiichiro Oda"},
                    },
                    {
                        "type": "cover_art",
                        "attributes": {"fileName": "cover123.jpg"},
                    },
                ],
            }
        ],
        "total": 1,
    }


def _manga_detail_response() -> dict:
    return {
        "result": "ok",
        "data": {
            "id": "a1c7c817-4e59-43b7-9365-09675a149a6f",
            "type": "manga",
            "attributes": {
                "title": {"en": "One Piece"},
                "description": {"en": "A pirate adventure."},
                "status": "ongoing",
                "year": 1997,
                "publicationDemographic": "shounen",
                "tags": [
                    {"attributes": {"name": {"en": "Action"}}},
                ],
            },
            "relationships": [
                {
                    "type": "author",
                    "attributes": {"name": "Eiichiro Oda"},
                },
                {
                    "type": "artist",
                    "attributes": {"name": "Eiichiro Oda"},
                },
                {
                    "type": "cover_art",
                    "attributes": {"fileName": "cover123.jpg"},
                },
            ],
        },
    }


def _feed_response() -> dict:
    return {
        "result": "ok",
        "data": [
            {
                "id": "ch-001",
                "type": "chapter",
                "attributes": {
                    "volume": "1",
                    "chapter": "1",
                    "title": "Romance Dawn",
                    "publishAt": "1997-07-22T00:00:00+00:00",
                    "pages": 53,
                },
            },
            {
                "id": "ch-002",
                "type": "chapter",
                "attributes": {
                    "volume": "1",
                    "chapter": "2",
                    "title": "That Guy, Straw Hat Luffy",
                    "publishAt": "1997-08-04T00:00:00+00:00",
                    "pages": 23,
                },
            },
            {
                "id": "ch-003",
                "type": "chapter",
                "attributes": {
                    "volume": "2",
                    "chapter": "9",
                    "title": "Femme Fatale",
                    "publishAt": "1997-11-04T00:00:00+00:00",
                    "pages": 19,
                },
            },
        ],
        "total": 3,
    }


@pytest.mark.asyncio
async def test_mangadex_search(monkeypatch):
    async def fake_request(self, path, params=None):
        assert path == "manga"
        return _manga_search_response()

    monkeypatch.setattr(MangaDexProvider, "_request", fake_request)

    results = await MangaDexProvider().search("One Piece")

    assert len(results) == 1
    assert results[0].provider == "mangadex"
    assert results[0].provider_item_id == "a1c7c817-4e59-43b7-9365-09675a149a6f"
    assert results[0].title == "One Piece"
    assert results[0].kind == ItemKind.manga
    assert "shounen" in results[0].summary
    assert "cover123.jpg" in results[0].image_url


@pytest.mark.asyncio
async def test_mangadex_get_item_and_normalize(monkeypatch):
    async def fake_request(self, path, params=None):
        return _manga_detail_response()

    monkeypatch.setattr(MangaDexProvider, "_request", fake_request)

    provider = MangaDexProvider()
    item = await provider.get_item("a1c7c817-4e59-43b7-9365-09675a149a6f")
    normalized = await provider.normalize(item.raw)

    assert item.provider_item_id == "a1c7c817-4e59-43b7-9365-09675a149a6f"
    assert normalized.kind == ItemKind.manga
    assert normalized.title == "One Piece"
    assert normalized.synopsis == "A pirate adventure."
    assert normalized.edition_format == "Manga"
    assert any(c.name == "Eiichiro Oda" and c.role == "Author" for c in normalized.creators)
    assert any(c.name == "Eiichiro Oda" and c.role == "Artist" for c in normalized.creators)
    assert any(a.name == "Action" for a in normalized.story_arcs)


@pytest.mark.asyncio
async def test_mangadex_get_volumes(monkeypatch):
    async def fake_request(self, path, params=None):
        if "feed" in path:
            return _feed_response()
        return _manga_detail_response()

    monkeypatch.setattr(MangaDexProvider, "_request", fake_request)

    volumes = await MangaDexProvider().get_volumes("a1c7c817-4e59-43b7-9365-09675a149a6f")

    assert len(volumes) == 2
    assert volumes[0].season_number == 1
    assert volumes[0].title == "Volume 1"
    assert volumes[0].episode_count == 2
    assert len(volumes[0].episodes) == 2
    assert volumes[0].episodes[0].episode_number == 1
    assert volumes[0].episodes[0].title == "Romance Dawn"
    assert volumes[0].episodes[1].episode_number == 2
    assert volumes[0].episodes[1].title == "That Guy, Straw Hat Luffy"
    assert volumes[1].season_number == 2
    assert volumes[1].title == "Volume 2"
    assert len(volumes[1].episodes) == 1
    assert volumes[1].episodes[0].episode_number == 9
    assert volumes[1].episodes[0].title == "Femme Fatale"


@pytest.mark.asyncio
async def test_anilist_get_volumes(monkeypatch):
    from app.providers.anilist import AniListProvider

    async def fake_graphql(self, query, variables):
        return {"data": {"Media": {"volumes": 3, "chapters": 30}}}

    monkeypatch.setattr(AniListProvider, "_graphql", fake_graphql)

    volumes = await AniListProvider().get_volumes("12345")

    assert len(volumes) == 3
    assert volumes[0].season_number == 1
    assert volumes[0].title == "Volume 1"
    assert volumes[2].season_number == 3
    assert volumes[2].title == "Volume 3"
    assert all(v.episodes == [] for v in volumes)
