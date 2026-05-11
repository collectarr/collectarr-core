import pytest

from tests.helpers import seed_comic


@pytest.mark.asyncio
async def test_search_falls_back_to_postgres(client):
    item_id, _, _ = await seed_comic()

    response = await client.get("/search", params={"q": "spider", "kind": "comic"})
    assert response.status_code == 200
    assert response.json()[0]["id"] == item_id

    detail = await client.get(f"/comics/{item_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "The Amazing Spider-Man"

