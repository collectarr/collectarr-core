import pytest

from app.db.session import AsyncSessionLocal
from app.models import AdminReleaseMediaMappingRule, MetadataProposal
from app.models.base import ExternalProvider, ItemKind
from app.schemas.admin import ProviderIngestHistoryEntry
from app.services.admin_domains import support as support_module

from .test_admin_providers import admin_token


@pytest.mark.asyncio
async def test_admin_can_crud_release_mapping_rules(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    public = await client.get("/admin/metadata/mapping-rules")
    assert public.status_code == 200
    assert public.json() == []

    created = await client.post(
        "/admin/metadata/mapping-rules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "comicvine",
            "release_type": "Issue",
            "target_kind": "comic",
            "priority": 10,
            "is_active": True,
            "notes": "Comic issue links to comic media",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["provider"] == "comicvine"
    assert body["release_type"] == "issue"
    assert body["target_kind"] == "comic"
    rule_id = body["id"]

    duplicate = await client.post(
        "/admin/metadata/mapping-rules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "comicvine",
            "release_type": "issue",
            "target_kind": "comic",
        },
    )
    assert duplicate.status_code == 409

    updated = await client.patch(
        f"/admin/metadata/mapping-rules/{rule_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": None, "priority": 5},
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["provider"] is None
    assert updated_body["priority"] == 5

    listed = await client.get("/admin/metadata/mapping-rules")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = await client.delete(
        f"/admin/metadata/mapping-rules/{rule_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}


@pytest.mark.asyncio
async def test_provider_prefill_resolve_uses_proposal_and_mapping_rule(client, monkeypatch):
    await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        rule = AdminReleaseMediaMappingRule(
            provider=None,
            release_type="issue",
            target_kind=ItemKind.comic,
            priority=1,
            is_active=True,
        )
        proposal = MetadataProposal(
            provider=ExternalProvider.comicvine,
            provider_item_id="4000-12345",
            query="Amazing Spider-Man",
            title="Amazing Spider-Man #1",
            metadata_payload={"candidate_type": "issue"},
        )
        db.add(rule)
        db.add(proposal)
        await db.commit()
        proposal_id = str(proposal.id)

    resolved = await client.post(
        "/admin/providers/prefill/resolve",
        json={
            "source": "proposal",
            "proposal_id": proposal_id,
        },
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["provider"] == "comicvine"
    assert body["provider_item_id"] == "4000-12345"
    assert body["query"] == "Amazing Spider-Man"
    assert body["release_type"] == "issue"
    assert body["kind"] == "comic"
    assert body["matched_rule"] is not None
    assert body["matched_rule"]["target_kind"] == "comic"


@pytest.mark.asyncio
async def test_provider_prefill_resolve_uses_ingest_history(client):
    support_module._INGEST_HISTORY.appendleft(
        ProviderIngestHistoryEntry(
            id=4242,
            timestamp=support_module.datetime.now(support_module.UTC),
            provider=ExternalProvider.tmdb,
            provider_item_id="movie-4242",
            status="created",
            attempts=1,
        )
    )
    resolved = await client.post(
        "/admin/providers/prefill/resolve",
        json={
            "source": "ingest_history",
            "ingest_history_id": 4242,
        },
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["provider"] == "tmdb"
    assert body["provider_item_id"] == "movie-4242"
