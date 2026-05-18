import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.models.canonical import ExternalProviderId, Item, Organization, Person, Tag
from app.providers.base import ProviderItem
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
        "runtime": 136,
        "poster_path": "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
        "genres": [{"name": "Science Fiction"}, {"name": "Action"}],
        "production_companies": [{"name": "Warner Bros. Pictures"}],
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
        assert params["append_to_response"] == "credits,external_ids,recommendations"
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
    assert normalized.story_arcs[0].name == "Science Fiction"
    assert normalized.provider_ids == {"tmdb": "movie:603"}


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
    assert normalized.provider_ids == {"tmdb": "tv:1399"}


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
    assert normalized.edition_format == "Anime"
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
    assert body["item"]["publisher"] == "Warner Bros. Pictures"
    assert body["item"]["runtime_minutes"] == 136

    async with AsyncSessionLocal() as db:
        item = await db.scalar(select(Item).where(Item.kind == ItemKind.movie))
        provider_ids = list(await db.scalars(select(ExternalProviderId.provider_item_id)))
        publisher = await db.scalar(select(Organization.name))
        creator = await db.scalar(select(Person.name))
        tags = set(await db.scalars(select(Tag.name)))

    assert item is not None
    assert provider_ids == ["movie:603"]
    assert publisher == "Warner Bros. Pictures"
    assert creator == "Lana Wachowski"
    assert "Keanu Reeves" in tags
    assert "Science Fiction" in tags
