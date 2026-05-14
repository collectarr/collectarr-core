import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.canonical import MetadataProposal
from app.providers.comicvine import ComicVineProvider

from .helpers import register_and_login
from .test_admin_ingest import comicvine_issue_raw


@pytest.mark.asyncio
async def test_provider_search_requires_login(client):
    response = await client.get("/metadata/providers/comicvine/search", params={"q": "spider"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_provider_search_returns_comicvine_results(client, monkeypatch):
    token = await register_and_login(client)

    async def fake_search(self, query, kind=None):
        assert query == "spider"
        return [ComicVineProvider()._search_result(comicvine_issue_raw())]

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)

    response = await client.get(
        "/metadata/providers/comicvine/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "spider"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["provider"] == "comicvine"
    assert body[0]["provider_item_id"] == "4000-12345"
    assert body[0]["title"] == "The Amazing Spider-Man #1 The Spider Strikes"


@pytest.mark.asyncio
async def test_provider_search_rejects_provider_for_wrong_kind(client):
    token = await register_and_login(client)

    response = await client.get(
        "/metadata/providers/comicvine/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "spider", "kind": "book"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Provider 'comicvine' does not support kind 'book'"


@pytest.mark.asyncio
async def test_provider_search_returns_planned_provider_stub(client):
    token = await register_and_login(client)

    response = await client.get(
        "/metadata/providers/tmdb/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "the matrix"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["provider"] == "tmdb"
    assert body[0]["provider_item_id"] == "stub-movie-the-matrix"
    assert body[0]["kind"] == "movie"


@pytest.mark.asyncio
async def test_metadata_proposal_is_saved_without_user_collection_data(client):
    token = await register_and_login(client)

    response = await client.post(
        "/metadata/proposals",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "comicvine",
            "provider_item_id": "4000-12345",
            "query": "missing spider-man issue",
            "title": "The Amazing Spider-Man #1 The Spider Strikes",
            "summary": "Candidate metadata from ComicVine.",
            "image_url": "https://example.test/cover.jpg",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["provider"] == "comicvine"

    async with AsyncSessionLocal() as db:
        proposal = await db.scalar(select(MetadataProposal))
        assert proposal is not None
        assert proposal.query == "missing spider-man issue"
        assert proposal.title == "The Amazing Spider-Man #1 The Spider Strikes"


@pytest.mark.asyncio
async def test_metadata_proposal_requires_explicit_provider(client):
    token = await register_and_login(client)

    response = await client.post(
        "/metadata/proposals",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "missing metadata",
            "title": "No provider fallback",
        },
    )

    assert response.status_code == 422
