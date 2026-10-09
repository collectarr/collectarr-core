from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import DuplicateReview
from app.models.catalog_comic_item import ComicItem
from app.search.client import SearchClient
from tests.helpers import seed_comic


async def admin_token(client, monkeypatch) -> str:
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})
    response = await client.post(
        "/api/v1/auth/register",
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
    item_id = await seed_comic()

    response = await client.patch(
        f"/api/v1/admin/catalog/items/comic/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "The Amazing Spider-Man Deluxe"},
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
    assert body[0]["entity_type"] == "comic"
    assert body[0]["entity_id"] == item_id
    assert body[0]["details_json"]["fields"] == ["title"]
    assert body[0]["details_json"]["after"]["title"] == "The Amazing Spider-Man Deluxe"

    item_logs = await client.get(
        "/api/v1/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"entity_type": "comic", "entity_id": item_id},
    )

    assert item_logs.status_code == 200
    assert [row["id"] for row in item_logs.json()] == [body[0]["id"]]


@pytest.mark.asyncio
async def test_admin_duplicate_merge_endpoint_is_disabled(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    async with AsyncSessionLocal() as db:
        target = ComicItem(title="Duplicate Book", sort_key="duplicate book", details={})
        source = ComicItem(title="Duplicate Book", sort_key="duplicate book", details={})
        db.add_all([target, source])
        await db.commit()
        target_id = str(target.id)
        source_id = str(source.id)

    merge = await client.post(
        "/api/v1/admin/duplicates/merge",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_item_id": target_id, "source_item_ids": [source_id]},
    )

    assert merge.status_code == 404

    async with AsyncSessionLocal() as db:
        remaining = list(
            await db.scalars(
                select(ComicItem).where(ComicItem.id.in_([UUID(target_id), UUID(source_id)]))
            )
        )
    assert {str(row.id) for row in remaining} == {target_id, source_id}


@pytest.mark.asyncio
async def test_admin_duplicate_ignore_endpoint_records_audit_context(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    async with AsyncSessionLocal() as db:
        first = ComicItem(title="Review Me", sort_key="review me", details={})
        second = ComicItem(title="Review Me", sort_key="review me", details={})
        db.add_all([first, second])
        await db.commit()
        item_ids = [str(first.id), str(second.id)]

    review = await client.post(
        "/api/v1/admin/duplicates/ignore",
        headers={"Authorization": f"Bearer {token}"},
        json={"item_ids": item_ids},
    )

    assert review.status_code == 200
    assert review.json() == {"ok": True, "affected_items": 2}

    async with AsyncSessionLocal() as db:
        review_row = await db.scalar(
            select(DuplicateReview)
            .options(selectinload(DuplicateReview.entities))
            .where(DuplicateReview.action == "ignore")
        )

    assert review_row is not None
    assert review_row.ignore_token is not None
    assert [str(row.entity_id) for row in review_row.entities] == item_ids

    logs = await client.get(
        "/api/v1/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"action": "duplicates.ignore"},
    )
    assert logs.status_code == 200
    row = logs.json()[0]
    assert row["details_json"]["decision"] == "ignore"
    assert row["details_json"]["item_ids"] == item_ids
    assert row["details_json"]["duplicate_score"] >= 55
