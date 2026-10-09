from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models import CanonicalCorrectionProposal, User, UserRole
from app.models.catalog_book_item import BookItem
from app.models.catalog_music_item import MusicItem
from app.schemas.canonical_corrections import CanonicalCorrectionProposalCreate
from app.services.canonical_corrections import CanonicalCorrectionService


@pytest.mark.asyncio
async def test_canonical_correction_proposal_is_targeted_without_entity_resolution(client):
    entity_id = uuid4()
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        db.add(BookItem(id=entity_id, title="Original title", details={}))
        await db.commit()

    snapshot = await client.get(
        f"/api/v1/metadata/correction-targets/book/{entity_id}",
        params={"scope": "catalog_item"},
    )
    assert snapshot.status_code == 200
    snapshot_body = snapshot.json()
    response = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={
            "kind": "book",
            "entity_type": "catalog_book_item",
            "entity_id": str(entity_id),
            "scope": "catalog_item",
            "base_hash": snapshot_body["hash"],
            "proposed_fields": {"title": "A corrected title"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["entity_id"] == str(entity_id)
    assert body["entity_type"] == "catalog_book_item"
    assert body["scope"] == "catalog_item"
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
        "entity_type": "catalog_book_item",
        "entity_id": str(uuid4()),
        "scope": "catalog_item",
        "base_revision": "42",
    }

    owned = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={**base, "proposed_fields": {"owned": True}},
    )
    provider_only = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={**base, "proposed_fields": {"provider_item_id": "external-1"}},
    )

    assert owned.status_code == 422
    assert owned.json()["code"] == "invalid_canonical_correction_target"
    assert provider_only.status_code == 422
    assert provider_only.json()["code"] == "invalid_canonical_correction_target"


def test_canonical_correction_requires_a_base_and_forbids_provider_metadata():
    with pytest.raises(ValidationError):
        CanonicalCorrectionProposalCreate(
            kind="book",
            entity_type="catalog_book_item",
            entity_id=uuid4(),
            scope="catalog_item",
            proposed_fields={"title": "Title"},
        )

    with pytest.raises(ValidationError):
        CanonicalCorrectionProposalCreate(
            kind="book",
            entity_type="catalog_book_item",
            entity_id=uuid4(),
            scope="catalog_item",
            base_hash="hash",
            provider="openlibrary",
            proposed_fields={"title": "Title"},
        )


@pytest.mark.asyncio
async def test_canonical_correction_rejects_stale_snapshot_and_approves_exact_target(client):
    entity_id = uuid4()
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        db.add(BookItem(id=entity_id, title="Before", details={}))
        await db.commit()

    snapshot = await client.get(
        f"/api/v1/metadata/correction-targets/book/{entity_id}",
        params={"scope": "catalog_item"},
    )
    base = snapshot.json()
    proposal = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={
            "kind": "book",
            "entity_type": "catalog_book_item",
            "entity_id": str(entity_id),
            "scope": "catalog_item",
            "base_hash": base["hash"],
            "proposed_fields": {"title": "After"},
        },
    )
    assert proposal.status_code == 201

    async with AsyncSessionLocal() as db:
        entity = await db.get(BookItem, entity_id)
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

        entity = await db.get(BookItem, entity_id)
        assert entity is not None
        assert entity.title == "Changed elsewhere"


@pytest.mark.asyncio
async def test_music_nested_correction_fields_are_canonical_and_correction_only(client):
    entity_id = uuid4()
    disc_ids = [str(uuid4()), str(uuid4())]
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        db.add(
            MusicItem(
                id=entity_id,
                title="Deluxe Edition",
                artist_credits=[{"id": "artist-credit-1", "name": "The Band", "sequence": 1}],
                credits=[
                    {
                        "id": "album-credit-1",
                        "name": "John Example",
                        "role": "Producer",
                        "sequence": 1,
                        "instruments": [],
                    }
                ],
                discs=[
                    {
                        "id": disc_ids[0],
                        "disc_number": 1,
                        "format_family": "opticalDisc",
                        "format": "CD",
                        "sound_types": [],
                        "recording_locations": [],
                        "credits": [],
                        "tracks": [],
                    },
                    {
                        "id": disc_ids[1],
                        "disc_number": 2,
                        "format_family": "opticalDisc",
                        "format": "CD",
                        "sound_types": [],
                        "recording_locations": [],
                        "credits": [],
                        "tracks": [],
                    },
                ],
            )
        )
        await db.commit()

    snapshot = await client.get(
        f"/api/v1/metadata/correction-targets/music/{entity_id}",
        params={"scope": "catalog_item"},
    )
    assert snapshot.status_code == 200
    body = snapshot.json()
    fields = {field["key"]: field for field in body["field_schema"]}
    assert fields["artist_credits"]["value_type"] == "object_list"
    assert fields["credits"]["value_type"] == "object_list"
    assert fields["discs"]["value_type"] == "object_list"
    assert [disc["id"] for disc in body["fields"]["discs"]] == disc_ids

    metadata = await client.get("/api/v1/metadata/field-schema", params={"editable_only": "false"})
    assert metadata.status_code == 200
    metadata_body = metadata.json()
    metadata_keys = {field["key"] for field in metadata_body["fields"]}
    music_keys = set(metadata_body["kind_fields"]["music"])
    assert not {"artist_credits", "credits", "discs"} & metadata_keys
    assert not {"artist_credits", "credits", "discs"} & music_keys

    proposal = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={
            "kind": "music",
            "entity_type": "catalog_music_item",
            "entity_id": str(entity_id),
            "scope": "catalog_item",
            "base_hash": body["hash"],
            "proposed_fields": {
                "credits": [
                    {
                        "id": "album-credit-1",
                        "name": "John A. Example",
                        "role": "Producer",
                        "sequence": 1,
                        "instruments": [],
                    }
                ],
                "discs": [
                    {
                        "id": disc_ids[0],
                        "disc_number": 1,
                        "format_family": "opticalDisc",
                        "format": "CD",
                        "title": "First Disc",
                        "sound_types": [],
                        "recording_locations": [],
                        "credits": [],
                        "tracks": [],
                    },
                    {
                        "id": disc_ids[1],
                        "disc_number": 2,
                        "format_family": "opticalDisc",
                        "format": "CD",
                        "sound_types": [],
                        "recording_locations": [],
                        "credits": [],
                        "tracks": [],
                    },
                ],
            },
        },
    )
    assert proposal.status_code == 201
    diff = proposal.json()["diff"]
    assert diff["credits"]["before"][0]["id"] == "album-credit-1"
    assert diff["credits"]["after"][0]["id"] == "album-credit-1"
    assert [disc["id"] for disc in diff["discs"]["after"]] == disc_ids


@pytest.mark.asyncio
async def test_music_nested_correction_rejects_invalid_or_duplicate_component_ids(client):
    entity_id = uuid4()
    disc_id = str(uuid4())
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        db.add(
            MusicItem(
                id=entity_id,
                title="Album",
                discs=[
                    {
                        "id": disc_id,
                        "disc_number": 1,
                        "sound_types": [],
                        "recording_locations": [],
                        "credits": [],
                        "tracks": [],
                    }
                ],
            )
        )
        await db.commit()

    snapshot = await client.get(
        f"/api/v1/metadata/correction-targets/music/{entity_id}",
        params={"scope": "catalog_item"},
    )
    proposal = await client.post(
        "/api/v1/metadata/correction-proposals",
        json={
            "kind": "music",
            "entity_type": "catalog_music_item",
            "entity_id": str(entity_id),
            "scope": "catalog_item",
            "base_hash": snapshot.json()["hash"],
            "proposed_fields": {
                "discs": [
                    {
                        "id": disc_id,
                        "disc_number": 1,
                        "sound_types": [],
                        "recording_locations": [],
                        "credits": [],
                        "tracks": [],
                    },
                    {
                        "id": disc_id,
                        "disc_number": 2,
                        "sound_types": [],
                        "recording_locations": [],
                        "credits": [],
                        "tracks": [],
                    },
                ]
            },
        },
    )
    assert proposal.status_code == 422
    assert proposal.json()["code"] == "invalid_canonical_music_payload"
