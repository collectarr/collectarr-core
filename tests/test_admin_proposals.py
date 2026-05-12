import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider
from app.models.canonical import MetadataProposal

from .test_admin_ui import admin_token


@pytest.mark.asyncio
async def test_admin_can_list_and_reject_metadata_proposals(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    async with AsyncSessionLocal() as db:
        proposal = MetadataProposal(
            provider=ExternalProvider.comicvine,
            provider_item_id="4000-12345",
            query="spider",
            title="The Amazing Spider-Man #1",
        )
        db.add(proposal)
        await db.commit()
        proposal_id = str(proposal.id)

    unauthorized = await client.get("/admin/metadata/proposals")
    assert unauthorized.status_code == 401

    response = await client.get(
        "/admin/metadata/proposals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()[0]["id"] == proposal_id
    assert response.json()[0]["status"] == "pending"

    reject = await client.post(
        f"/admin/metadata/proposals/{proposal_id}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    async with AsyncSessionLocal() as db:
        status = await db.scalar(select(MetadataProposal.status))
        assert status == "rejected"
