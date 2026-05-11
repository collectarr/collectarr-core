from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers import register_and_login, seed_comic


@pytest.mark.asyncio
async def test_sync_push_pull_and_tombstone(client):
    item_id, edition_id, variant_id = await seed_comic()
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    changed_at = datetime.now(UTC)

    pushed = await client.post(
        "/sync/push",
        headers=headers,
        json={
            "device_id": "desktop-01",
            "changes": [
                {
                    "entity_type": "owned_item",
                    "action": "upsert",
                    "device_id": "desktop-01",
                    "client_changed_at": changed_at.isoformat(),
                    "payload": {
                        "item_id": item_id,
                        "edition_id": edition_id,
                        "variant_id": variant_id,
                        "condition": "Fine",
                    },
                }
            ],
        },
    )
    assert pushed.status_code == 200
    owned_id = pushed.json()["changes"][0]["entity_id"]
    assert pushed.json()["changes"][0]["device_id"] == "desktop-01"

    pull = await client.post(
        "/sync/pull",
        headers=headers,
        json={"since": (changed_at - timedelta(minutes=1)).isoformat()},
    )
    assert pull.status_code == 200
    assert len(pull.json()["collection"]) == 1

    deleted = await client.post(
        "/sync/push",
        headers=headers,
        json={
            "device_id": "phone-01",
            "changes": [
                {
                    "entity_type": "owned_item",
                    "entity_id": owned_id,
                    "action": "delete",
                    "client_changed_at": datetime.now(UTC).isoformat(),
                    "payload": {},
                }
            ],
        },
    )
    assert deleted.status_code == 200
    assert deleted.json()["changes"][0]["action"] == "delete"

    changes = await client.get("/sync/changes", headers=headers)
    assert len(changes.json()) == 2


@pytest.mark.asyncio
async def test_sync_stale_client_update_loses_to_newer_server_state(client):
    item_id, edition_id, variant_id = await seed_comic()
    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    newer_time = datetime.now(UTC)
    older_time = newer_time - timedelta(minutes=10)

    first = await client.post(
        "/sync/push",
        headers=headers,
        json={
            "device_id": "desktop-01",
            "changes": [
                {
                    "entity_type": "owned_item",
                    "action": "upsert",
                    "client_changed_at": newer_time.isoformat(),
                    "payload": {
                        "item_id": item_id,
                        "edition_id": edition_id,
                        "variant_id": variant_id,
                        "condition": "Near Mint",
                    },
                }
            ],
        },
    )
    assert first.status_code == 200
    owned_id = first.json()["changes"][0]["entity_id"]

    stale = await client.post(
        "/sync/push",
        headers=headers,
        json={
            "device_id": "phone-01",
            "changes": [
                {
                    "entity_type": "owned_item",
                    "entity_id": owned_id,
                    "action": "upsert",
                    "client_changed_at": older_time.isoformat(),
                    "payload": {
                        "item_id": item_id,
                        "edition_id": edition_id,
                        "variant_id": variant_id,
                        "condition": "Poor",
                    },
                }
            ],
        },
    )
    assert stale.status_code == 200
    assert stale.json()["changes"][0]["payload"]["condition"] == "Near Mint"
