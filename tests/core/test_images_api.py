import base64
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.base import UserRole
from app.models.canonical import ImageAsset
from app.repositories.users import UserRepository

from tests.helpers import register_and_login


async def _register_and_login_admin(client, email: str = "admin@example.com") -> str:
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "display_name": "Admin"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]

    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_email(email)
        assert user is not None
        user.is_admin = True
        user.role = UserRole.admin
        await db.commit()

    return token


@pytest.mark.asyncio
async def test_add_entity_image_rejects_unknown_entity_type(client):
    token = await _register_and_login_admin(client)

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
async def test_add_entity_image_requires_admin(client):
    token = await register_and_login(client)

    response = await client.post(
        f"/images/entity/item/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "image_type": "front_cover",
            "image_data_base64": base64.b64encode(b"fake-image").decode("ascii"),
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "admin_required"


@pytest.mark.asyncio
async def test_add_entity_image_uses_content_hash_for_uploaded_source_url(
    client,
    monkeypatch,
):
    token = await _register_and_login_admin(client, email="image-admin@example.com")
    entity_id = uuid4()
    mirrored_keys: list[str] = []
    source_urls: list[str] = []

    class FakeStorage:
        def public_object_url(self, object_key: str) -> str:
            return f"https://storage.example/{object_key}"

    async def fake_mirror(self, image_bytes, *, source_url, provider, provider_item_id):
        source_urls.append(source_url)
        storage_key = f"covers/user/{provider_item_id}/{source_url.rsplit('/', 1)[-1]}.webp"
        mirrored_keys.append(storage_key)

        class Mirrored:
            key = storage_key
            width = 640
            height = 960

        return Mirrored()

    monkeypatch.setattr(
        "app.api.routes.images.ObjectStorage.shared",
        lambda: FakeStorage(),
    )
    monkeypatch.setattr(
        "app.api.routes.images.ImageMirror.mirror_cover_bytes_best_effort",
        fake_mirror,
    )

    first = await client.post(
        f"/images/entity/item/{entity_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "image_type": "front_cover",
            "image_data_base64": base64.b64encode(b"first-image").decode("ascii"),
        },
    )
    second = await client.post(
        f"/images/entity/item/{entity_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "image_type": "front_cover",
            "image_data_base64": base64.b64encode(b"second-image").decode("ascii"),
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert len(source_urls) == 2
    assert source_urls[0] != source_urls[1]
    assert mirrored_keys[0] != mirrored_keys[1]
    assert first.json()["source_url"] == source_urls[0]
    assert second.json()["source_url"] == source_urls[1]

    async with AsyncSessionLocal() as db:
        rows = list(
            await db.scalars(
                    select(ImageAsset).where(
                    ImageAsset.entity_type == "item",
                    ImageAsset.entity_id == entity_id,
                )
            )
        )

    assert len(rows) == 2
    assert {row.source_url for row in rows} == set(source_urls)


@pytest.mark.asyncio
async def test_delete_image_requires_admin(client):
    token = await register_and_login(client)
    image_id = uuid4()

    async with AsyncSessionLocal() as db:
        db.add(
            ImageAsset(
                id=image_id,
                entity_type="item",
                entity_id=uuid4(),
                image_type="front_cover",
                storage_key="covers/user/item/front.webp",
                provider="user",
            )
        )
        await db.commit()

    response = await client.delete(
        f"/images/{image_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "admin_required"


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
