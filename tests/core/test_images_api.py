import base64
from uuid import uuid4

import pytest

from app.db.session import AsyncSessionLocal
from app.models.canonical import ImageAsset

from tests.helpers import register_and_login


@pytest.mark.asyncio
async def test_add_entity_image_rejects_unknown_entity_type(client):
    token = await register_and_login(client)

    response = await client.post(
        f"/images/entity/not-a-real-type/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "image_type": "front_cover",
            "image_data_base64": base64.b64encode(b"fake-image").decode("ascii"),
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_entity_type"


@pytest.mark.asyncio
async def test_download_image_rejects_untracked_object_key(client, monkeypatch):
    token = await register_and_login(client)
    requested: list[str] = []

    class FakeStorage:
        def get_object(self, object_key: str):
            requested.append(object_key)
            return b"secret", "image/webp"

    monkeypatch.setattr("app.api.routes.images.ObjectStorage.shared", lambda: FakeStorage())

    response = await client.get(
        "/images/download",
        headers={"Authorization": f"Bearer {token}"},
        params={"object_key": "private/config.env"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "image_not_found"
    assert requested == []


@pytest.mark.asyncio
async def test_download_image_allows_authorized_image_asset_key(client, monkeypatch):
    token = await register_and_login(client)
    object_key = "covers/comicvine/4000-1/cover.webp"

    async with AsyncSessionLocal() as db:
        db.add(
            ImageAsset(
                entity_type="item",
                entity_id=uuid4(),
                image_type="front_cover",
                storage_key=object_key,
                provider="comicvine",
            )
        )
        await db.commit()

    class FakeStorage:
        def get_object(self, requested_key: str):
            assert requested_key == object_key
            return b"image-bytes", "image/webp"

    monkeypatch.setattr("app.api.routes.images.ObjectStorage.shared", lambda: FakeStorage())

    response = await client.get(
        "/images/download",
        headers={"Authorization": f"Bearer {token}"},
        params={"object_key": object_key},
    )

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"].startswith("image/webp")


@pytest.mark.asyncio
async def test_batch_download_images_returns_none_for_untracked_keys(client, monkeypatch):
    token = await register_and_login(client)
    allowed_key = "covers/comicvine/4000-2/cover.webp"
    blocked_key = "backups/users.sql"

    async with AsyncSessionLocal() as db:
        db.add(
            ImageAsset(
                entity_type="item",
                entity_id=uuid4(),
                image_type="front_cover",
                storage_key=allowed_key,
                provider="comicvine",
            )
        )
        await db.commit()

    requested: list[str] = []

    class FakeStorage:
        def get_object(self, requested_key: str):
            requested.append(requested_key)
            return b"batch-image", "image/webp"

    monkeypatch.setattr("app.api.routes.images.ObjectStorage.shared", lambda: FakeStorage())

    response = await client.post(
        "/images/batch-download",
        headers={"Authorization": f"Bearer {token}"},
        json=[allowed_key, blocked_key],
    )

    assert response.status_code == 200
    assert response.json()[allowed_key] == base64.b64encode(b"batch-image").decode("ascii")
    assert response.json()[blocked_key] is None
    assert requested == [allowed_key]
