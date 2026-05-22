import pytest

from app.core.config import get_settings
from app.models.base import UserRole
from app.repositories.users import UserRepository
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_register_and_login(client):
    response = await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123", "display_name": "User"},
    )
    assert response.status_code == 201
    assert response.json()["token_type"] == "bearer"

    login = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


@pytest.mark.asyncio
async def test_current_user_returns_profile(client):
    response = await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]

    current = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert current.status_code == 200
    assert current.json()["email"] == "user@example.com"
    assert current.json()["is_admin"] is False
    assert current.json()["role"] == UserRole.viewer.value


@pytest.mark.asyncio
async def test_current_user_requires_bearer_token(client):
    response = await client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "missing_bearer_token"


@pytest.mark.asyncio
async def test_bootstrap_admin_email_registers_admin(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})

    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )

    assert response.status_code == 201
    assert response.json()["user"]["is_admin"] is True
    assert response.json()["user"]["role"] == UserRole.admin.value


@pytest.mark.asyncio
async def test_current_user_reconciles_legacy_admin_role_flags(client):
    response = await client.post(
        "/auth/register",
        json={"email": "legacy@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]

    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_email("legacy@example.com")
        assert user is not None
        user.is_admin = True
        user.role = UserRole.viewer
        await db.commit()

    current = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert current.status_code == 200
    assert current.json()["is_admin"] is True
    assert current.json()["role"] == UserRole.admin.value
