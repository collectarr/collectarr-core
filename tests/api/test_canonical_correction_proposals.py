from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models import CanonicalCorrectionProposal
from app.schemas.canonical_corrections import CanonicalCorrectionProposalCreate


@pytest.mark.asyncio
async def test_canonical_correction_proposal_is_targeted_without_entity_resolution(client):
    entity_id = uuid4()
    response = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={
            "kind": "book",
            "entity_type": "book_work",
            "entity_id": str(entity_id),
            "scope": "work",
            "base_hash": "sha256:before",
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

    from app.db.session import AsyncSessionLocal

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
    assert provider_only.json()["code"] == "invalid_canonical_correction_target"


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
