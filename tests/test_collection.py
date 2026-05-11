import pytest

from tests.helpers import register_and_login, seed_comic


@pytest.mark.asyncio
async def test_collection_crud(client):
    item_id, edition_id, variant_id = await seed_comic()
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/collection/add",
        headers=headers,
        json={
            "item_id": item_id,
            "edition_id": edition_id,
            "variant_id": variant_id,
            "condition": "Near Mint",
        },
    )
    assert created.status_code == 201
    owned_id = created.json()["id"]

    listed = await client.get("/collection", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    patched = await client.patch(
        f"/collection/{owned_id}",
        headers=headers,
        json={"grade": "9.4", "personal_notes": "Local shop"},
    )
    assert patched.status_code == 200
    assert patched.json()["grade"] == "9.4"

    deleted = await client.delete(f"/collection/{owned_id}", headers=headers)
    assert deleted.status_code == 204

    listed_after_delete = await client.get("/collection", headers=headers)
    assert listed_after_delete.json() == []

