import pytest

from app.core.config import get_settings


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
async def test_bootstrap_admin_email_registers_admin(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})

    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )

    assert response.status_code == 201
    assert response.json()["user"]["is_admin"] is True
