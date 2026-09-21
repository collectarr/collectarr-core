from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models import BookWork, CanonicalCorrectionProposal, User, UserRole
from app.schemas.canonical_corrections import CanonicalCorrectionProposalCreate
from app.services.canonical_corrections import CanonicalCorrectionService


@pytest.mark.asyncio
async def test_canonical_correction_proposal_is_targeted_without_entity_resolution(client):
    entity_id = uuid4()
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        db.add(BookWork(id=entity_id, title="Original title"))
        await db.commit()

    snapshot = await client.get(
        f"/api/v1/metadata/correction-targets/book/{entity_id}",
        params={"scope": "work"},
    )
    assert snapshot.status_code == 200
    snapshot_body = snapshot.json()
    response = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={
            "kind": "book",
            "entity_type": "book_work",
            "entity_id": str(entity_id),
            "scope": "work",
            "base_hash": snapshot_body["hash"],
            "proposed_fields": {"title": "A corrected title"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["entity_id"] == str(entity_id)
    assert body["entity_type"] == "book_work"
    assert body["scope"] == "work"
    assert body["proposed_fields"] == {"title": "A corrected title"}
    assert body["status"] == "pending"
    assert body["current_fields"]["title"] == "Original title"
    assert body["diff"]["title"] == {
        "before": "Original title",
        "after": "A corrected title",
    }
    assert body["current_hash"] == snapshot_body["hash"]

    async with AsyncSessionLocal() as db:
        stored = await db.get(CanonicalCorrectionProposal, UUID(body["id"]))
        assert stored is not None
        assert stored.entity_id == entity_id


@pytest.mark.asyncio
async def test_canonical_correction_rejects_owned_and_provider_fields(client):
    base = {
        "kind": "book",
        "entity_type": "book_work",
        "entity_id": str(uuid4()),
        "scope": "work",
        "base_revision": "42",
    }

    owned = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={**base, "proposed_fields": {"owned": True}},
    )
    provider_only = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={**base, "proposed_fields": {"physical_format": "cd"}},
    )

    assert owned.status_code == 422
    assert owned.json()["code"] == "invalid_canonical_correction_target"
    assert provider_only.status_code == 422
    assert provider_only.json()["code"] in {
        "canonical_correction_scope_mismatch",
        "canonical_correction_entity_type_mismatch",
    }


def test_canonical_correction_requires_a_base_and_forbids_provider_metadata():
    with pytest.raises(ValidationError):
        CanonicalCorrectionProposalCreate(
            kind="book",
            entity_type="book_work",
            entity_id=uuid4(),
            scope="work",
            proposed_fields={"title": "Title"},
        )

    with pytest.raises(ValidationError):
        CanonicalCorrectionProposalCreate(
            kind="book",
            entity_type="book_work",
            entity_id=uuid4(),
            scope="work",
            base_hash="hash",
            provider="openlibrary",
            proposed_fields={"title": "Title"},
        )


@pytest.mark.asyncio
async def test_canonical_correction_rejects_stale_snapshot_and_approves_exact_target(client):
    entity_id = uuid4()
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        db.add(BookWork(id=entity_id, title="Before"))
        await db.commit()

    snapshot = await client.get(
        f"/api/v1/metadata/correction-targets/book/{entity_id}",
        params={"scope": "work"},
    )
    base = snapshot.json()
    proposal = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={
            "kind": "book",
            "entity_type": "book_work",
            "entity_id": str(entity_id),
            "scope": "work",
            "base_hash": base["hash"],
            "proposed_fields": {"title": "After"},
        },
    )
    assert proposal.status_code == 201

    async with AsyncSessionLocal() as db:
        entity = await db.get(BookWork, entity_id)
        assert entity is not None
        entity.title = "Changed elsewhere"
        await db.commit()

        actor = User(
            email="admin@example.test",
            password_hash="test",
            role=UserRole.admin,
            entity_type="user",
        )
        db.add(actor)
        await db.commit()

    async with AsyncSessionLocal() as db:
        with pytest.raises(Exception) as error:
            await CanonicalCorrectionService(db).approve(
                UUID(proposal.json()["id"]),
                actor=actor,
            )
        assert "stale" in str(error.value).lower()

        entity = await db.get(BookWork, entity_id)
        assert entity is not None
        assert entity.title == "Changed elsewhere"
