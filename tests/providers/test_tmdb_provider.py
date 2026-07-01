from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.models import (
    ExternalProviderId,
    MovieRelease,
    MovieReleaseMedia,
    MovieWork,
    MovieWorkContribution,
    MovieWorkIdentifier,
    TVRelease,
    TVReleaseMedia,
)
from app.providers.base import NormalizedItem, ProviderItem
from app.providers.tmdb import TMDbProvider
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


def _movie_raw() -> dict:
    return {
        "id": 603,
        "media_type": "movie",
        "title": "The Matrix",
        "original_title": "The Matrix",
        "overview": "A hacker discovers the nature of reality.",
        "release_date": "1999-03-31",
        "vote_average": 8.7,
        "runtime": 136,
        "poster_path": "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
        "genres": [{"name": "Science Fiction"}, {"name": "Action"}],
        "production_companies": [{"name": "Warner Bros. Pictures"}],
        "external_ids": {
            "imdb_id": "tt0133093",
            "tmdb_id": 603,
        },
        "videos": {
            "results": [
                {
                    "site": "YouTube",
                    "type": "Trailer",
                    "key": "vKQi3bBA1y8",
                    "name": "Official Trailer",
                }
            ]
        },
        "release_dates": [
            {
                "iso_3166_1": "US",
                "release_dates": [
                    {"certification": "R"},
                ],
            }
        ],
        "credits": {
            "crew": [
                {"name": "Lana Wachowski", "job": "Director"},
                {"name": "Lilly Wachowski", "job": "Writer"},
            ],
            "cast": [
                {"name": "Keanu Reeves", "character": "Neo"},
            ],
        },
    }


def _tv_raw() -> dict:
    return {
        "id": 1399,
        "media_type": "tv",
        "name": "Game of Thrones",
        "original_name": "Game of Thrones",
        "overview": "Noble families fight for control.",
        "first_air_date": "2011-04-17",
        "vote_average": 8.4,
        "episode_run_time": [60],
        "poster_path": "/u3bZgnGQ9T01sWNhyveQz0wH0Hl.jpg",
        "genres": [{"name": "Drama"}],
        "production_companies": [{"name": "HBO"}],
        "created_by": [{"name": "David Benioff"}, {"name": "D. B. Weiss"}],
        "credits": {
            "cast": [
                {"name": "Emilia Clarke", "character": "Daenerys Targaryen"},
            ],
        },
        "seasons": [
            {
                "season_number": 1,
                "name": "Season 1",
                "overview": "The first season.",
                "air_date": "2011-04-17",
                "episode_count": 10,
                "poster_path": "/season-1.jpg",
            },
            {
                "season_number": 2,
                "name": "Season 2",
                "overview": "The second season.",
                "air_date": "2012-04-01",
                "episode_count": 10,
                "poster_path": "/season-2.jpg",
            },
        ],
    }


def _anime_raw() -> dict:
    raw = _tv_raw()
    raw.update(
        {
            "id": 37854,
            "media_type": "anime",
            "name": "One Piece",
            "original_name": "One Piece",
            "overview": "A rubber pirate searches for treasure.",
            "first_air_date": "1999-10-20",
            "episode_run_time": [24],
            "production_companies": [{"name": "Toei Animation"}],
            "created_by": [{"name": "Eiichiro Oda"}],
        }
    )
    return raw


@pytest.mark.asyncio
async def test_tmdb_provider_returns_stub_without_credentials():
    results = await TMDbProvider().search("The Matrix")

    assert len(results) == 1
    assert results[0].provider_item_id == "stub-movie-the-matrix"
    assert results[0].kind == ItemKind.movie


@pytest.mark.asyncio
async def test_tmdb_provider_searches_movies_tv_and_anime(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_read_access_token", "token")

    async def fake_request(self, path, params=None):
        assert params["query"] == "The Matrix"
        if path == "search/movie":
            return {"results": [_movie_raw()]}
        if path == "search/tv":
            return {"results": [_tv_raw()]}
        raise AssertionError(path)

    monkeypatch.setattr(TMDbProvider, "_request", fake_request)

    movies = await TMDbProvider().search(" The Matrix ", ItemKind.movie)
    tv = await TMDbProvider().search(" The Matrix ", ItemKind.tv)
    anime = await TMDbProvider().search(" The Matrix ", ItemKind.anime)

    assert movies[0].provider_item_id == "movie:603"
    assert movies[0].kind == ItemKind.movie
    assert movies[0].image_url == (
        "https://image.tmdb.org/t/p/w500/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg"
    )
    assert tv[0].provider_item_id == "tv:1399"
    assert tv[0].kind == ItemKind.tv
    assert anime[0].provider_item_id == "anime:1399"
    assert anime[0].kind == ItemKind.anime


@pytest.mark.asyncio
async def test_tmdb_provider_fetches_and_normalizes_movie(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_read_access_token", "token")

    async def fake_request(self, path, params=None):
        assert path == "movie/603"
        assert params["append_to_response"] == "credits,external_ids,recommendations,release_dates,videos"
        return _movie_raw()

    monkeypatch.setattr(TMDbProvider, "_request", fake_request)

    item = await TMDbProvider().get_item("movie:603")
    normalized = await TMDbProvider().normalize(item.raw)

    assert item.provider_item_id == "movie:603"
    assert normalized.kind == ItemKind.movie
    assert normalized.title == "The Matrix"
    assert normalized.publisher == "Warner Bros. Pictures"
    assert normalized.release_date.isoformat() == "1999-03-31"
    assert normalized.runtime_minutes == 136
    assert normalized.edition_format == "Movie"
    assert normalized.creators[0].name == "Lana Wachowski"
    assert normalized.characters[0].name == "Keanu Reeves"
    assert normalized.story_arcs == []
    assert normalized.audience_rating == "8.7"
    assert normalized.age_rating == "R"
    assert normalized.provider_ids == {"tmdb": "movie:603"}
    assert normalized.external_ids == {"tmdb_id": "603", "imdb_id": "tt0133093"}
    assert normalized.trailer_urls[0]["url"].endswith("vKQi3bBA1y8")
    assert normalized.external_links[0]["kind"] == "tmdb"


@pytest.mark.asyncio
async def test_tmdb_provider_fetches_and_normalizes_tv(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_read_access_token", "token")

    async def fake_request(self, path, params=None):
        assert path == "tv/1399"
        return _tv_raw()

    monkeypatch.setattr(TMDbProvider, "_request", fake_request)

    item = await TMDbProvider().get_item("tv:1399")
    normalized = await TMDbProvider().normalize(item.raw)

    assert item.provider_item_id == "tv:1399"
    assert normalized.kind == ItemKind.tv
    assert normalized.title == "Game of Thrones"
    assert normalized.publisher == "HBO"
    assert normalized.release_date.isoformat() == "2011-04-17"
    assert normalized.runtime_minutes == 60
    assert normalized.edition_format == "TV Series"
    assert normalized.creators[0].role == "Creator"
    assert normalized.audience_rating == "8.4"
    assert normalized.provider_ids == {"tmdb": "tv:1399"}


@pytest.mark.asyncio
async def test_tmdb_provider_get_seasons_includes_provider_item_ids(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_read_access_token", "token")

    async def fake_request(self, path, params=None):
        if path == "tv/1399":
            return _tv_raw()
        if path == "tv/1399/season/1":
            return {
                "episodes": [
                    {
                        "episode_number": 1,
                        "name": "Winter Is Coming",
                        "overview": "The North remembers.",
                        "air_date": "2011-04-17",
                        "runtime": 62,
                        "still_path": "/ep1.jpg",
                    }
                ]
            }
        if path == "tv/1399/season/2":
            return {"episodes": []}
        raise AssertionError(path)

    monkeypatch.setattr(TMDbProvider, "_request", fake_request)

    seasons = await TMDbProvider().get_seasons("tv:1399")

    assert len(seasons) == 2
    assert seasons[0].provider_item_id == "tv:1399:season:1"
    assert seasons[0].episodes[0].provider_item_id == "tv:1399:season:1:episode:1"
    assert seasons[0].episodes[0].runtime_minutes == 62


@pytest.mark.asyncio
async def test_tmdb_provider_emits_season_pack_bundle_for_multi_season_show(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_read_access_token", "token")

    async def fake_request(self, path, params=None):
        assert path == "tv/1399"
        return _tv_raw()

    monkeypatch.setattr(TMDbProvider, "_request", fake_request)

    item = await TMDbProvider().get_item("tv:1399")
    normalized = await TMDbProvider().normalize(item.raw)

    assert normalized.bundle_release is not None
    assert normalized.bundle_release.bundle_type == "season_pack"
    assert normalized.bundle_release.provider_ids == {"tmdb": "tv:1399"}
    assert [member.item.title for member in normalized.bundle_release.members] == [
        "Season 1",
        "Season 2",
    ]
    assert normalized.bundle_release.members[0].item.provider_ids == {
        "tmdb": "tv:1399#season-1"
    }


@pytest.mark.asyncio
async def test_tmdb_provider_fetches_and_normalizes_anime(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_read_access_token", "token")

    async def fake_request(self, path, params=None):
        assert path == "tv/37854"
        return _anime_raw()

    monkeypatch.setattr(TMDbProvider, "_request", fake_request)

    item = await TMDbProvider().get_item("anime:37854")
    normalized = await TMDbProvider().normalize(item.raw)

    assert item.provider_item_id == "anime:37854"
    assert normalized.kind == ItemKind.anime
    assert normalized.title == "One Piece"
    assert normalized.publisher == "Toei Animation"
    assert normalized.release_date.isoformat() == "1999-10-20"
    assert normalized.runtime_minutes == 24
    assert normalized.edition_format == "Anime Series"
    assert normalized.creators[0].role == "Creator"
    assert normalized.provider_ids == {"tmdb": "anime:37854"}


@pytest.mark.asyncio
async def test_admin_ingest_upserts_tmdb_movie(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="tmdb", provider_item_id="movie:603", raw=_movie_raw())

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(TMDbProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "tmdb", "provider_item_id": "movie:603"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["kind"] == "movie"
    assert body["item"]["title"] == "The Matrix"
    assert body["item"]["runtime_minutes"] == 136
    assert body["item"]["trailer_urls"][0]["site"] == "YouTube"
    assert body["item"]["external_links"][0]["kind"] == "tmdb"

    async with AsyncSessionLocal() as db:
        movie_work = await db.scalar(select(MovieWork).where(MovieWork.title == "The Matrix"))
        contributions = list(
            await db.scalars(
                select(MovieWorkContribution)
                .join(MovieWork)
                .where(MovieWork.title == "The Matrix")
                .order_by(MovieWorkContribution.sequence.asc())
            )
        )
        identifiers = list(
            await db.scalars(
                select(MovieWorkIdentifier)
                .join(MovieWork)
                .where(MovieWork.title == "The Matrix")
                .order_by(MovieWorkIdentifier.identifier_type.asc())
            )
        )
        release = await db.scalar(
            select(MovieRelease).join(MovieWork).where(MovieWork.title == "The Matrix")
        )
        provider_ids = list(
            await db.scalars(
                select(ExternalProviderId.provider_item_id).where(
                    ExternalProviderId.entity_type == "movie_work"
                )
            )
        )
    assert movie_work is not None
    assert movie_work.metadata_json["trailer_urls"][0]["kind"] == "trailer"
    assert movie_work.metadata_json["external_links"][0]["kind"] == "tmdb"
    assert any(row.role == "cast" and row.character_name == "Neo" for row in contributions)
    assert {row.identifier_type for row in identifiers} >= {"provider_item_id", "imdb_id", "tmdb_id"}
    assert provider_ids == ["movie:603"]
    assert release is not None


@pytest.mark.asyncio
async def test_admin_ingest_persists_tv_media_color(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="tmdb", provider_item_id="tv:1399", raw=_tv_raw())

    async def fake_normalize(self, raw):
        return NormalizedItem(
            kind=ItemKind.tv,
            title="Game of Thrones",
            edition_title="Game of Thrones",
            edition_format="TV Series",
            release_date=date(2011, 4, 17),
            runtime_minutes=60,
            age_rating="TV-MA",
            audience_rating="8.4",
            screen_ratio="16:9",
            color="Color",
            audio_tracks="English Dolby",
            subtitles="English, Romanian",
            layers="BD-50",
            provider_ids={"tmdb": "tv:1399"},
        )

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(TMDbProvider, "get_item", fake_get_item)
    monkeypatch.setattr(TMDbProvider, "normalize", fake_normalize)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "tmdb", "provider_item_id": "tv:1399"},
    )

    assert response.status_code == 201
    body = response.json()["item"]
    assert body["kind"] == "tv"
    assert body["media"][0]["color"] == "Color"

    async with AsyncSessionLocal() as db:
        release = await db.scalar(select(TVRelease).where(TVRelease.title == "Game of Thrones"))
        media = await db.scalar(select(TVReleaseMedia).join(TVRelease).where(TVRelease.title == "Game of Thrones"))

    assert release is not None
    assert media is not None
    assert media.aspect_ratio == "16:9"
    assert media.color == "Color"
    assert media.audio_tracks == "English Dolby"
    assert media.subtitles == "English, Romanian"
    assert media.layers == "BD-50"


@pytest.mark.asyncio
async def test_admin_ingest_persists_movie_release_color(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="tmdb", provider_item_id="movie:603", raw=_movie_raw())

    async def fake_normalize(self, raw):
        return NormalizedItem(
            kind=ItemKind.movie,
            title="The Matrix",
            edition_format="Movie",
            release_date=date(1999, 3, 31),
            runtime_minutes=136,
            age_rating="R",
            audience_rating="8.7",
            screen_ratio="2.39:1",
            color="Color",
            audio_tracks="English Dolby Atmos",
            subtitles="English, Romanian",
            layers="BD-50",
            provider_ids={"tmdb": "movie:603"},
            trailer_urls=[{"site": "YouTube", "type": "Trailer", "key": "vKQi3bBA1y8", "name": "Official Trailer"}],
            external_links=[{"kind": "tmdb", "url": "https://www.themoviedb.org/movie/603"}],
        )

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(TMDbProvider, "get_item", fake_get_item)
    monkeypatch.setattr(TMDbProvider, "normalize", fake_normalize)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "tmdb", "provider_item_id": "movie:603"},
    )

    assert response.status_code == 201
    body = response.json()["item"]
    assert body["kind"] == "movie"
    assert body["releases"][0]["media"][0]["color"] == "Color"

    async with AsyncSessionLocal() as db:
        releases = (
            await db.execute(select(MovieRelease).join(MovieWork).where(MovieWork.title == "The Matrix"))
        ).scalars().all()
        media_rows = (
            await db.execute(select(MovieReleaseMedia).join(MovieRelease).join(MovieWork).where(MovieWork.title == "The Matrix"))
        ).scalars().all()

    release = next((row for row in releases if row.color == "Color"), None)
    media = next((row for row in media_rows if row.aspect_ratio == "2.39:1"), None)

    assert release is not None
    assert media is not None
    assert media.audio_tracks == "English Dolby Atmos"
    assert media.subtitles == "English, Romanian"
    assert media.layers == "BD-50"
@pytest.mark.asyncio
async def test_tmdb_provider_get_seasons(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "tmdb_api_read_access_token", "token")

    async def fake_request(self, path, params=None):
        if path == "tv/1399":
            return {
                "id": 1399,
                "seasons": [
                    {
                        "season_number": 1,
                        "name": "Season 1",
                        "overview": "The first season.",
                        "air_date": "2011-04-17",
                        "episode_count": 10,
                        "poster_path": "/season1.jpg",
                    },
                    {
                        "season_number": 2,
                        "name": "Season 2",
                        "overview": "The second season.",
                        "air_date": "2012-04-01",
                        "episode_count": 10,
                        "poster_path": "/season2.jpg",
                    },
                ],
            }
        if path == "tv/1399/season/1":
            return {
                "episodes": [
                    {
                        "episode_number": 1,
                        "name": "Winter Is Coming",
                        "overview": "Ned Stark is called south.",
                        "air_date": "2011-04-17",
                        "runtime": 62,
                        "still_path": "/ep1.jpg",
                    },
                    {
                        "episode_number": 2,
                        "name": "The Kingsroad",
                        "overview": "The party heads south.",
                        "air_date": "2011-04-24",
                        "runtime": 56,
                        "still_path": "/ep2.jpg",
                    },
                ],
            }
        if path == "tv/1399/season/2":
            return {
                "episodes": [
                    {
                        "episode_number": 1,
                        "name": "The North Remembers",
                        "overview": "Tyrion arrives at court.",
                        "air_date": "2012-04-01",
                        "runtime": 53,
                        "still_path": "/ep3.jpg",
                    },
                ],
            }
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(TMDbProvider, "_request", fake_request)

    seasons = await TMDbProvider().get_seasons("tv:1399")

    assert len(seasons) == 2
    assert seasons[0].season_number == 1
    assert seasons[0].title == "Season 1"
    assert seasons[0].overview == "The first season."
    assert seasons[0].episode_count == 10
    assert seasons[0].poster_url == "https://image.tmdb.org/t/p/w500/season1.jpg"
    assert len(seasons[0].episodes) == 2
    assert seasons[0].episodes[0].episode_number == 1
    assert seasons[0].episodes[0].title == "Winter Is Coming"
    assert seasons[0].episodes[0].runtime_minutes == 62
    assert seasons[0].episodes[0].still_url == "https://image.tmdb.org/t/p/w500/ep1.jpg"
    assert seasons[1].season_number == 2
    assert len(seasons[1].episodes) == 1
