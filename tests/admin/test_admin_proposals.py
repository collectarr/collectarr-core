from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models import MetadataProposal
from app.models.base import ExternalProvider


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
async def test_admin_can_list_and_reject_metadata_proposals(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    async with AsyncSessionLocal() as db:
        proposal = MetadataProposal(
            provider=ExternalProvider.comicvine,
            provider_item_id="4000-12345",
            query="spider",
            title="The Amazing Spider-Man #1",
            metadata_payload={
                "kind": "comic",
                "genres": None,
                "platforms": None,
                "cover_image_url": "https://example.test/spider.jpg",
                "nested": {"a": None, "b": "ok"},
            },
        )
        tmdb_proposal = MetadataProposal(
            provider=ExternalProvider.tmdb,
            provider_item_id="movie-1",
            query="spider",
            title="Spider Movie",
        )
        approved_proposal = MetadataProposal(
            provider=ExternalProvider.comicvine,
            provider_item_id="4000-99999",
            query="batman",
            title="Batman #1",
            status="approved",
        )
        db.add(proposal)
        db.add(tmdb_proposal)
        db.add(approved_proposal)
        await db.commit()
        proposal_id = str(proposal.id)
        tmdb_proposal_id = str(tmdb_proposal.id)

    public = await client.get("/admin/metadata/proposals")
    assert public.status_code == 200

    response = await client.get(
        "/admin/metadata/proposals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {proposal_id, tmdb_proposal_id}
    assert {item["status"] for item in response.json()} == {"pending"}
    payload_by_id = {item["id"]: item["metadata_payload"] for item in response.json()}
    assert payload_by_id[proposal_id] == {
        "kind": "comic",
        "cover_image_url": "https://example.test/spider.jpg",
        "nested": {"b": "ok"},
    }

    comicvine_response = await client.get(
        "/admin/metadata/proposals?provider=comicvine",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert comicvine_response.status_code == 200
    assert [item["id"] for item in comicvine_response.json()] == [proposal_id]

    summary = await client.get(
        "/admin/metadata/proposals/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert summary.status_code == 200
    assert summary.json() == {"pending": 2, "approved": 1, "rejected": 0, "total": 3}

    reject = await client.post(
        f"/admin/metadata/proposals/{proposal_id}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    async with AsyncSessionLocal() as db:
        status = await db.scalar(
            select(MetadataProposal.status).where(MetadataProposal.id == UUID(proposal_id))
        )
        assert status == "rejected"
