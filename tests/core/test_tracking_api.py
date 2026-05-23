from uuid import UUID

import pytest

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind, UserRole
from app.models.canonical import Item, TrackingEntry
from app.repositories.users import UserRepository


async def _register_user(client, email: str, password: str = "password123") -> str:
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


async def _user_id(email: str) -> UUID:
    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_email(email)
        assert user is not None
        return user.id


async def _make_admin(email: str) -> str:
    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_email(email)
        assert user is not None
        user.role = UserRole.admin
        user.is_admin = True
        await db.commit()
        return create_access_token(user.id)


async def _create_item(title: str, kind: ItemKind = ItemKind.movie) -> Item:
    async with AsyncSessionLocal() as db:
        item = Item(kind=kind, title=title)
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item


async def _create_tracking_entry(
    *,
    user_id: UUID,
    item_id: UUID,
    source_type: str,
    status: str,
    rating: int | None = None,
) -> TrackingEntry:
    async with AsyncSessionLocal() as db:
        entry = TrackingEntry(
            user_id=user_id,
            item_id=item_id,
            source_type=source_type,
            status=status,
            rating=rating,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry


@pytest.mark.asyncio
async def test_tracking_entry_crud_and_item_stats(client):
    token = await _register_user(client, "tracking@example.com")
    item = await _create_item("Dune", kind=ItemKind.movie)

    created = await client.post(
        "/tracking/entries",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "item_id": str(item.id),
            "source_type": "digital",
            "status": "Watching",
            "rating": 8,
            "progress_current": 45,
            "progress_total": 100,
        },
    )

    assert created.status_code == 200
    created_json = created.json()
    assert created_json["item_title"] == "Dune"
    assert created_json["kind"] == "movie"

    entries = await client.get(
        "/tracking/entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert entries.status_code == 200
    assert len(entries.json()) == 1

    detail_stats = await client.get(
        f"/tracking/items/{item.id}/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_stats.status_code == 200
    detail_json = detail_stats.json()
    assert detail_json["total_entries"] == 1
    assert detail_json["unique_users"] == 1
    assert detail_json["average_rating"] == 8.0
    assert detail_json["current_user_entry"]["status"] == "Watching"
    assert detail_json["counts_by_status"] == [{"key": "Watching", "count": 1}]
    assert detail_json["counts_by_source_type"] == [{"key": "digital", "count": 1}]

    deleted = await client.delete(
        f"/tracking/entries/{created_json['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 204

    remaining = await client.get(
        "/tracking/entries",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert remaining.status_code == 200
    assert remaining.json() == []


@pytest.mark.asyncio
async def test_tracking_dashboard_and_admin_stats(client):
    user_token = await _register_user(client, "dash@example.com")
    await _register_user(client, "admin@example.com")
    admin_token = await _make_admin("admin@example.com")

    movie = await _create_item("Blade Runner 2049", kind=ItemKind.movie)
    album = await _create_item("Discovery", kind=ItemKind.music)
    user_id = await _user_id("dash@example.com")
    admin_user_id = await _user_id("admin@example.com")

    await _create_tracking_entry(
        user_id=user_id,
        item_id=movie.id,
        source_type="digital",
        status="Completed",
        rating=9,
    )
    await _create_tracking_entry(
        user_id=user_id,
        item_id=album.id,
        source_type="streaming",
        status="Listening",
        rating=8,
    )
    await _create_tracking_entry(
        user_id=admin_user_id,
        item_id=movie.id,
        source_type="digital",
        status="Watching",
        rating=7,
    )

    dashboard = await client.get(
        "/tracking/dashboard",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert dashboard.status_code == 200
    dashboard_json = dashboard.json()
    assert dashboard_json["total_entries"] == 2
    assert dashboard_json["average_rating"] == 8.5
    assert {row["kind"]: row["count"] for row in dashboard_json["counts_by_kind"]} == {
        "movie": 1,
        "music": 1,
    }
    assert {row["key"]: row["count"] for row in dashboard_json["counts_by_status"]} == {
        "Completed": 1,
        "Listening": 1,
    }

    admin_stats = await client.get(
        "/admin/tracking/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_stats.status_code == 200
    admin_json = admin_stats.json()
    assert admin_json["total_entries"] == 3
    assert admin_json["unique_users"] == 2
    assert admin_json["unique_items"] == 2
    assert admin_json["average_rating"] == 8.0
    assert admin_json["top_items"][0]["title"] == "Blade Runner 2049"
    assert admin_json["top_items"][0]["count"] == 2

    filtered_dashboard = await client.get(
        "/tracking/dashboard?kind=movie&source_type=digital&status=Completed",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert filtered_dashboard.status_code == 200
    filtered_dashboard_json = filtered_dashboard.json()
    assert filtered_dashboard_json["total_entries"] == 1
    assert filtered_dashboard_json["counts_by_kind"] == [{"kind": "movie", "count": 1}]

    dashboard_facets = await client.get(
        "/tracking/dashboard/facets?source_type=digital",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert dashboard_facets.status_code == 200
    dashboard_facets_json = dashboard_facets.json()
    assert dashboard_facets_json["counts_by_source_type"] == [{"key": "digital", "count": 1}]
    assert len(dashboard_facets_json["counts_by_period"]) >= 1

    admin_facets = await client.get(
        "/admin/tracking/facets?kind=movie",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_facets.status_code == 200
    admin_facets_json = admin_facets.json()
    assert admin_facets_json["counts_by_kind"] == [{"kind": "movie", "count": 2}]