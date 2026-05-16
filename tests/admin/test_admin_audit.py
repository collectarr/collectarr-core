from uuid import UUID

import pytest

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.models.canonical import Item
from app.search.client import SearchClient
from tests.helpers import seed_comic


async def admin_token(client, monkeypatch) -> str:
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})
    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_audit_logs_catalog_correction(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    item_id, _, _ = await seed_comic()

    response = await client.patch(
        f"/admin/catalog/items/comic/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "The Amazing Spider-Man Deluxe"},
    )

    assert response.status_code == 200

    logs = await client.get(
        "/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"action": "metadata.correction"},
    )

    assert logs.status_code == 200
    body = logs.json()
    assert len(body) == 1
    assert body[0]["actor_email"] == "admin@example.com"
    assert body[0]["entity_type"] == "item"
    assert body[0]["entity_id"] == item_id
    assert body[0]["details_json"]["fields"] == ["title"]
    assert body[0]["details_json"]["after"]["title"] == "The Amazing Spider-Man Deluxe"

    item_logs = await client.get(
        "/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"entity_type": "item", "entity_id": item_id},
    )

    assert item_logs.status_code == 200
    assert [row["id"] for row in item_logs.json()] == [body[0]["id"]]


@pytest.mark.asyncio
async def test_admin_audit_logs_duplicate_merge_and_job_create(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    async with AsyncSessionLocal() as db:
        target = Item(
            kind=ItemKind.comic,
            title="Duplicate Book",
            item_number="1",
            sort_key="duplicate-book-001",
        )
        source = Item(
            kind=ItemKind.comic,
            title="Duplicate Book",
            item_number="1",
            sort_key="duplicate-book-001-b",
        )
        db.add_all([target, source])
        await db.commit()
        target_id = str(target.id)
        source_id = str(source.id)

    merge = await client.post(
        "/admin/duplicates/merge",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_item_id": target_id, "source_item_ids": [source_id]},
    )

    assert merge.status_code == 200

    queued = await client.post(
        "/admin/providers/ingest/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "gcd", "provider_item_id": "256114"},
    )

    assert queued.status_code == 201
    job_id = queued.json()["id"]

    logs = await client.get(
        "/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 5},
    )

    assert logs.status_code == 200
    rows = {row["action"]: row for row in logs.json()}
    assert rows["duplicates.merge"]["entity_id"] == target_id
    assert rows["duplicates.merge"]["details_json"]["source_item_ids"] == [source_id]
    assert rows["provider_ingest.job_create"]["entity_id"] == job_id
    assert rows["provider_ingest.job_create"]["details_json"]["provider_item_id"] == "256114"

    filtered = await client.get(
        "/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"entity_type": "provider_ingest_job"},
    )

    assert filtered.status_code == 200
    assert [UUID(row["entity_id"]) for row in filtered.json()] == [UUID(job_id)]
