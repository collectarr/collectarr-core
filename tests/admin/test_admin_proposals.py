from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider
from app.models.canonical import ComicWork, MetadataProposal
from app.providers.base import ProviderItem
from app.providers.comicvine import ComicVineProvider
from app.search.client import SearchClient
from app.storage.images import ImageMirror

from .test_admin_ingest import comicvine_issue_raw
from .test_admin_providers import admin_token


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


@pytest.mark.asyncio
async def test_admin_can_approve_manual_proposal_with_provider_item(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(
            provider="comicvine",
            provider_item_id=provider_item_id,
            raw=comicvine_issue_raw(),
        )

    async def fake_index_documents(self, documents):
        return True

    async def fake_mirror_cover(self, source_url, provider, provider_item_id):
        return None

    monkeypatch.setattr(ComicVineProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fake_mirror_cover)

    async with AsyncSessionLocal() as db:
        proposal = MetadataProposal(
            provider=ExternalProvider.comicvine,
            query="The Amazing Spider-Man #1",
            title="The Amazing Spider-Man",
            summary="Manual proposal from CSV import",
        )
        db.add(proposal)
        await db.commit()
        proposal_id = str(proposal.id)

    response = await client.post(
        f"/admin/metadata/proposals/{proposal_id}/approve-provider",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "provider_item_id": "4000-12345"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True
    assert body["item"]["title"] == "The Amazing Spider-Man"

    async with AsyncSessionLocal() as db:
        proposal = await db.get(MetadataProposal, UUID(proposal_id))
        assert proposal is not None
        assert proposal.status == "approved"
        assert proposal.provider == ExternalProvider.comicvine
        assert proposal.provider_item_id == "4000-12345"
        # For comics v1, we now create ComicWork instead of Item
        # Check that a ComicWork was created with the right title
        comic_work = await db.scalar(select(ComicWork))
        assert comic_work is not None
        assert comic_work.title == "The Amazing Spider-Man"
