import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import DuplicateReview


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
    created = await client.post(
        "/api/v1/metadata/catalog/items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "details": {
                "kind": "comic",
                "title": "The Amazing Spider-Man",
                "issue_number": "1",
            }
        },
    )
    assert created.status_code == 201
    item = created.json()
    item_id = item["id"]
    details = item["details"]
    details["title"] = "The Amazing Spider-Man Deluxe"

    response = await client.put(
        f"/api/v1/metadata/catalog/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"details": details},
    )

    assert response.status_code == 200

    logs = await client.get(
        "/api/v1/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"action": "metadata.correction"},
    )

    assert logs.status_code == 200
    body = logs.json()
    assert len(body) == 1
    assert body[0]["actor_email"] == "admin@example.com"
    assert body[0]["entity_type"] == "catalog_item"
    assert body[0]["entity_id"] == item_id
    assert body[0]["details_json"]["fields"] == ["title"]
    assert body[0]["details_json"]["after"]["title"] == "The Amazing Spider-Man Deluxe"

    item_logs = await client.get(
        "/api/v1/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"entity_type": "catalog_item", "entity_id": item_id},
    )

    assert item_logs.status_code == 200
    assert [row["id"] for row in item_logs.json()] == [body[0]["id"]]


@pytest.mark.asyncio
async def test_admin_duplicate_candidates_use_catalog_items(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    headers = {"Authorization": f"Bearer {token}"}
    item_ids = []
    for title in ("Duplicate Comic", "Duplicate Comic"):
        created = await client.post(
            "/api/v1/metadata/catalog/items",
            headers=headers,
            json={"details": {"kind": "comic", "title": title}},
        )
        assert created.status_code == 201
        item_ids.append(created.json()["id"])

    response = await client.get(
        "/api/v1/admin/duplicates",
        headers=headers,
    )

    assert response.status_code == 200
    candidate = next(row for row in response.json() if set(row["item_ids"]) == set(item_ids))
    assert candidate["kind"] == "comic"
    assert candidate["title"] == "Duplicate Comic"
    assert candidate["reason"] == "same kind and title"


@pytest.mark.asyncio
async def test_admin_duplicate_ignore_audits_catalog_items(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    headers = {"Authorization": f"Bearer {token}"}
    item_ids = []
    for title in ("Review Me", "Review Me"):
        created = await client.post(
            "/api/v1/metadata/catalog/items",
            headers=headers,
            json={"details": {"kind": "comic", "title": title}},
        )
        assert created.status_code == 201
        item_ids.append(created.json()["id"])

    review = await client.post(
        "/api/v1/admin/duplicates/ignore",
        headers={"Authorization": f"Bearer {token}"},
        json={"item_ids": item_ids},
    )

    assert review.status_code == 200
    assert review.json() == {"ok": True, "affected_items": 2}

    async with AsyncSessionLocal() as db:
        review_row = await db.scalar(
            select(DuplicateReview).where(DuplicateReview.action == "ignore")
        )

    assert review_row is not None
    assert review_row.ignore_token is not None
    assert review_row.entity_type == "catalog_item"

    logs = await client.get(
        "/api/v1/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"action": "duplicates.ignore"},
    )
    assert logs.status_code == 200
    row = logs.json()[0]
    assert row["details_json"]["decision"] == "ignore"
    assert row["details_json"]["item_ids"] == item_ids
    assert row["details_json"]["duplicate_score"] == 100
