import pytest

from tests.helpers import seed_comic


@pytest.mark.asyncio
async def test_search_falls_back_to_postgres(client, monkeypatch):
    async def unavailable_search(self, query, kind=None):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, _, _ = await seed_comic()

    response = await client.get("/search", params={"q": "spider", "kind": "comic"})
    assert response.status_code == 200
    assert response.json()[0]["id"] == item_id

    detail = await client.get(f"/comics/{item_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "The Amazing Spider-Man"


@pytest.mark.asyncio
async def test_lookup_comic_by_barcode(client, monkeypatch):
    async def unavailable_search(self, query, kind=None):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, _, _ = await seed_comic()

    response = await client.get("/barcode/75960604716100111", params={"kind": "comic"})

    assert response.status_code == 200
    assert response.json()["id"] == item_id
    assert response.json()["title"] == "The Amazing Spider-Man"


@pytest.mark.asyncio
async def test_lookup_barcode_returns_404_for_unknown_code(client):
    response = await client.get("/barcode/0000000000000", params={"kind": "comic"})

    assert response.status_code == 404
