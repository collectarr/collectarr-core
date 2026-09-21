import pytest

from app.commands.set_admin import set_user_role
from app.db.session import AsyncSessionLocal
from app.models.base import UserRole
from app.repositories.users import UserRepository


@pytest.mark.asyncio
async def test_set_user_role_grants_and_revokes_admin(client):
    await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert await set_user_role("USER@example.com", UserRole.admin) == 0
    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_email("user@example.com")
        assert user is not None
        assert user.role == UserRole.admin

    assert await set_user_role("user@example.com", UserRole.viewer) == 0
    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_email("user@example.com")
        assert user is not None
        assert user.role == UserRole.viewer


@pytest.mark.asyncio
async def test_set_user_role_reports_missing_user(capsys):
    assert await set_user_role("missing@example.com", UserRole.admin) == 1

    captured = capsys.readouterr()
    assert "No user found for missing@example.com" in captured.err
