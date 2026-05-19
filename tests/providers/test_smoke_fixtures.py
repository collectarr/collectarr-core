"""Smoke fixtures for every media-type × provider combination.

Each fixture carries a realistic API-response snippet and the expected
``ProviderSearchResult`` fields that the provider's ``search`` method
should produce.  The tests below monkeypatch the HTTP layer so no real
network calls are made, then verify the search → parse pipeline.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.models.base import ItemKind


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _patch_settings(monkeypatch, **overrides):
    settings = get_settings()
    for key, value in overrides.items():
        monkeypatch.setattr(settings, key, value)


# ---------------------------------------------------------------------------
# Comics  – ComicVine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comicvine_comic_search(monkeypatch):
    from app.providers.comicvine import ComicVineProvider

    _patch_settings(monkeypatch, comicvine_api_key="smoke-key")

    async def fake_request(self, path, params):
        if path == "search/":
            return {
                "results": [
                    {
                        "id": 160294,
                        "name": "Absolute Batman",
                        "start_year": "2024",
                        "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-160294/",
                        "publisher": {"name": "DC Comics"},
                        "count_of_issues": 6,
                        "image": {"super_url": "https://example.com/cover.jpg"},
                    }
                ]
            }
        return {"results": []}

    monkeypatch.setattr(ComicVineProvider, "_request", fake_request)
    results = await ComicVineProvider().search("Absolute Batman", kind=ItemKind.comic)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "comicvine"
    assert r.kind == ItemKind.comic
    assert "batman" in r.title.lower()


# ---------------------------------------------------------------------------
# Comics  – GCD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gcd_comic_search(monkeypatch):
    from app.providers.gcd import GCDProvider

    async def fake_get(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "results": [
                        {
                            "api_url": "https://www.comics.org/api/issue/12345/",
                            "series_name": "Amazing Spider-Man (2022 series)",
                            "number": "1",
                            "barcode": "75960620664100111",
                            "descriptor": "1",
                            "publication_date": "2022-04-27",
                            "publisher_name": "Marvel",
                            "price": "4.99 USD",
                            "page_count": "32.000",
                            "story_set": [],
                            "variant_of": None,
                        }
                    ]
                }

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    results = await GCDProvider().search("Amazing Spider-Man #1", kind=ItemKind.comic)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "gcd"
    assert r.kind == ItemKind.comic


# ---------------------------------------------------------------------------
# Manga – MangaDex
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mangadex_manga_search(monkeypatch):
    from app.providers.mangadex import MangaDexProvider

    async def fake_get(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "result": "ok",
                    "data": [
                        {
                            "id": "a1c7c817-4e59-43b7-9365-09675a149a6f",
                            "type": "manga",
                            "attributes": {
                                "title": {"en": "One Piece"},
                                "description": {"en": "A pirate adventure."},
                                "year": 1997,
                                "status": "ongoing",
                                "contentRating": "safe",
                                "tags": [],
                            },
                            "relationships": [
                                {
                                    "type": "cover_art",
                                    "attributes": {"fileName": "cover.jpg"},
                                }
                            ],
                        }
                    ],
                }

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    results = await MangaDexProvider().search("One Piece", kind=ItemKind.manga)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "mangadex"
    assert r.kind == ItemKind.manga
    assert "one piece" in r.title.lower()


# ---------------------------------------------------------------------------
# Manga / Anime – AniList
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anilist_manga_search(monkeypatch):
    from app.providers.anilist import AniListProvider

    async def fake_post(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "data": {
                        "Page": {
                            "media": [
                                {
                                    "id": 30013,
                                    "title": {
                                        "romaji": "One Piece",
                                        "english": "One Piece",
                                    },
                                    "format": "MANGA",
                                    "type": "MANGA",
                                    "description": "A pirate adventure manga.",
                                    "coverImage": {
                                        "large": "https://example.com/anilist-cover.jpg"
                                    },
                                    "startDate": {"year": 1997},
                                    "status": "RELEASING",
                                    "siteUrl": "https://anilist.co/manga/30013",
                                    "volumes": 108,
                                    "chapters": 1125,
                                }
                            ]
                        }
                    }
                }

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    results = await AniListProvider().search("One Piece", kind=ItemKind.manga)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "anilist"
    assert r.kind == ItemKind.manga


@pytest.mark.asyncio
async def test_anilist_anime_search(monkeypatch):
    from app.providers.anilist import AniListProvider

    async def fake_post(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "data": {
                        "Page": {
                            "media": [
                                {
                                    "id": 21,
                                    "title": {
                                        "romaji": "One Piece",
                                        "english": "One Piece",
                                    },
                                    "format": "TV",
                                    "type": "ANIME",
                                    "description": "Anime adaptation.",
                                    "coverImage": {
                                        "large": "https://example.com/anime.jpg"
                                    },
                                    "startDate": {"year": 1999},
                                    "status": "RELEASING",
                                    "siteUrl": "https://anilist.co/anime/21",
                                    "episodes": 1100,
                                }
                            ]
                        }
                    }
                }

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    results = await AniListProvider().search("One Piece", kind=ItemKind.anime)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "anilist"
    assert r.kind == ItemKind.anime


# ---------------------------------------------------------------------------
# Books – Open Library
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openlibrary_book_search(monkeypatch):
    from app.providers.openlibrary import OpenLibraryProvider

    async def fake_get(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "docs": [
                        {
                            "key": "/works/OL45804W",
                            "title": "Dune",
                            "author_name": ["Frank Herbert"],
                            "first_publish_year": 1965,
                            "isbn": ["9780441172719"],
                            "cover_i": 8228691,
                        }
                    ],
                    "numFound": 1,
                }

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    results = await OpenLibraryProvider().search("Dune", kind=ItemKind.book)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "openlibrary"
    assert r.kind == ItemKind.book
    assert "dune" in r.title.lower()


# ---------------------------------------------------------------------------
# Video – TMDb (movie + TV)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tmdb_movie_search(monkeypatch):
    from app.providers.tmdb import TMDbProvider

    _patch_settings(monkeypatch, tmdb_api_key="smoke-key")

    async def fake_get(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "results": [
                        {
                            "id": 438631,
                            "title": "Dune",
                            "media_type": "movie",
                            "overview": "A noble family...",
                            "release_date": "2021-09-15",
                            "poster_path": "/poster.jpg",
                        }
                    ]
                }

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    results = await TMDbProvider().search("Dune", kind=ItemKind.movie)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "tmdb"
    assert r.kind == ItemKind.movie


@pytest.mark.asyncio
async def test_tmdb_tv_search(monkeypatch):
    from app.providers.tmdb import TMDbProvider

    _patch_settings(monkeypatch, tmdb_api_key="smoke-key")

    async def fake_get(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "results": [
                        {
                            "id": 1399,
                            "name": "Game of Thrones",
                            "media_type": "tv",
                            "overview": "Seven noble families...",
                            "first_air_date": "2011-04-17",
                            "poster_path": "/got.jpg",
                        }
                    ]
                }

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    results = await TMDbProvider().search("Game of Thrones", kind=ItemKind.tv)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "tmdb"
    assert r.kind == ItemKind.tv


# ---------------------------------------------------------------------------
# Games – IGDB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_igdb_game_search(monkeypatch):
    from app.providers.igdb import IGDBProvider

    _patch_settings(
        monkeypatch,
        igdb_client_id="smoke-id",
        igdb_client_secret="smoke-secret",
    )

    async def fake_post(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return [
                    {
                        "id": 1942,
                        "name": "The Witcher 3: Wild Hunt",
                        "summary": "An RPG set in...",
                        "cover": {"image_id": "co1wyy"},
                        "first_release_date": 1431993600,
                        "platforms": [{"name": "PC"}],
                    }
                ]

            def raise_for_status(self):
                pass

        return _Resp()

    # IGDB needs an access token; mock the token fetch too
    async def fake_access_token(self):
        return "smoke-access-token"

    monkeypatch.setattr(IGDBProvider, "_access_token", fake_access_token)
    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    results = await IGDBProvider().search("Witcher 3", kind=ItemKind.game)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "igdb"
    assert r.kind == ItemKind.game


# ---------------------------------------------------------------------------
# Board Games – BGG
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bgg_boardgame_search(monkeypatch):
    from app.providers.bgg import BGGProvider

    async def fake_get(self, url, **kwargs):
        # BGG uses XML — check how the provider parses it
        class _Resp:
            status_code = 200
            text = """<?xml version="1.0" encoding="utf-8"?>
<items total="1">
  <item type="boardgame" id="174430">
    <name type="primary" value="Gloomhaven"/>
    <yearpublished value="2017"/>
    <thumbnail value="https://example.com/bgg-thumb.jpg"/>
  </item>
</items>"""

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    results = await BGGProvider().search("Gloomhaven", kind=ItemKind.boardgame)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "bgg"
    assert r.kind == ItemKind.boardgame


# ---------------------------------------------------------------------------
# Music – MusicBrainz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_musicbrainz_music_search(monkeypatch):
    from app.providers.musicbrainz import MusicBrainzProvider

    async def fake_get(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "releases": [
                        {
                            "id": "b84ee12a-09ef-421b-82de-0441a926375b",
                            "title": "OK Computer",
                            "artist-credit": [{"name": "Radiohead"}],
                            "date": "1997-05-21",
                            "country": "GB",
                        }
                    ]
                }

            def raise_for_status(self):
                pass

        return _Resp()

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)
    results = await MusicBrainzProvider().search("OK Computer", kind=ItemKind.music)

    assert len(results) >= 1
    r = results[0]
    assert r.provider == "musicbrainz"
    assert r.kind == ItemKind.music
