import pytest

from app.models.base import ItemKind
from app.providers.hardcover import HardcoverProvider


def _search_response() -> dict:
    return {
        "data": {
            "search": {
                "results": [
                    {
                        "document": {
                            "id": 42,
                            "title": "The Hobbit",
                            "author_names": ["J.R.R. Tolkien"],
                            "featured_series": {"name": "Middle-earth"},
                            "release_year": 1937,
                            "image": {"url": "https://cdn.example/hobbit.jpg"},
                        }
                    }
                ]
            }
        }
    }


def _book_response() -> dict:
    return {
        "data": {
            "books": [
                {
                    "id": 42,
                    "title": "The Hobbit",
                    "subtitle": "There and Back Again",
                    "description": "Bilbo leaves the Shire.",
                    "pages": 310,
                    "release_date": "1937-09-21",
                    "contributions": [
                        {
                            "author": {"name": "J.R.R. Tolkien"},
                            "contribution_type": "Author",
                        }
                    ],
                    "book_series": [
                        {
                            "series": {"id": 9, "name": "Middle-earth"},
                            "position": 2,
                        }
                    ],
                    "editions": [
                        {
                            "isbn_13": "9780618968633",
                            "pages": 320,
                            "edition_format": "Hardcover",
                            "publisher": {"name": "George Allen & Unwin"},
                            "image": {"url": "https://cdn.example/hobbit-ed.jpg"},
                        }
                    ],
                    "taggings": [
                        {"tag": {"tag": "Fantasy"}},
                    ],
                    "image": {"url": "https://cdn.example/hobbit.jpg"},
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_hardcover_search_preserves_requested_book_kind(monkeypatch):
    async def fake_graphql(self, query, variables=None):
        return _search_response()

    monkeypatch.setattr(HardcoverProvider, "_graphql", fake_graphql)

    results = await HardcoverProvider().search("The Hobbit", kind=ItemKind.book)

    assert len(results) == 1
    assert results[0].kind == ItemKind.book
    assert results[0].provider_item_id == "book:42"


@pytest.mark.asyncio
async def test_hardcover_get_item_and_normalize_preserves_book_kind(monkeypatch):
    async def fake_graphql(self, query, variables=None):
        return _book_response()

    monkeypatch.setattr(HardcoverProvider, "_graphql", fake_graphql)

    provider = HardcoverProvider()
    item = await provider.get_item("book:42")
    normalized = await provider.normalize(item.raw)

    assert item.provider_item_id == "book:42"
    assert normalized.kind == ItemKind.book
    assert normalized.edition_format == "Hardcover"
    assert normalized.page_count == 310
    assert normalized.provider_ids == {"hardcover": "book:42"}
    assert normalized.volume_provider_ids == {"hardcover": "book:42"}


@pytest.mark.asyncio
async def test_hardcover_get_volumes_preserves_requested_book_kind(monkeypatch):
    get_item_calls: list[str] = []

    async def fake_get_item(self, provider_item_id):
        get_item_calls.append(provider_item_id)

        class _ProviderItemStub:
            raw = {
                "book_series": [
                    {
                        "series": {"id": 9, "name": "Middle-earth"},
                        "position": 2,
                    }
                ]
            }

        return _ProviderItemStub()

    async def fake_graphql(self, query, variables=None):
        assert variables == {"seriesId": 9}
        return {
            "data": {
                "series": [
                    {
                        "name": "Middle-earth",
                        "book_series": [
                            {
                                "position": 1,
                                "book": {
                                    "title": "The Hobbit",
                                    "description": "Bilbo leaves the Shire.",
                                    "release_date": "1937-09-21",
                                    "pages": 310,
                                    "editions": [],
                                },
                            }
                        ],
                    }
                ]
            }
        }

    monkeypatch.setattr(HardcoverProvider, "get_item", fake_get_item)
    monkeypatch.setattr(HardcoverProvider, "_graphql", fake_graphql)

    seasons = await HardcoverProvider().get_volumes("book:42")

    assert get_item_calls == ["book:42"]
    assert len(seasons) == 1
    assert seasons[0].title == "Middle-earth"
    assert seasons[0].episodes[0].title == "The Hobbit"


@pytest.mark.asyncio
async def test_hardcover_graphql_reuses_client(monkeypatch):
    created_clients = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": {}}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.posts: list[tuple[str, dict, dict]] = []
            self.closed = False
            created_clients.append(self)

        async def post(self, url, json=None, headers=None):
            self.posts.append((url, json or {}, headers or {}))
            return FakeResponse()

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setattr("app.providers.hardcover.httpx.AsyncClient", FakeAsyncClient)

    await HardcoverProvider().aclose()
    provider = HardcoverProvider()
    await provider._graphql("query One")
    await provider._graphql("query Two")

    assert len(created_clients) == 1
    assert len(created_clients[0].posts) == 2

    await provider.aclose()
    assert created_clients[0].closed is True


@pytest.mark.asyncio
async def test_hardcover_graphql_shares_client_across_provider_instances(monkeypatch):
    created_clients = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": {}}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            self.posts: list[tuple[str, dict, dict]] = []
            self.closed = False
            created_clients.append(self)

        async def post(self, url, json=None, headers=None):
            self.posts.append((url, json or {}, headers or {}))
            return FakeResponse()

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setattr("app.providers.hardcover.httpx.AsyncClient", FakeAsyncClient)

    first = HardcoverProvider()
    second = HardcoverProvider()
    await first.aclose()

    await first._graphql("query One")
    await second._graphql("query Two")

    assert len(created_clients) == 1
    assert len(created_clients[0].posts) == 2

    await second.aclose()
    assert created_clients[0].closed is True