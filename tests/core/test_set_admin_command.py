import pytest

from app.commands.set_admin import set_admin_status
from app.db.session import AsyncSessionLocal
from app.repositories.users import UserRepository


@pytest.mark.asyncio
async def test_set_admin_status_grants_and_revokes_admin(client):
    await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert await set_admin_status("USER@example.com", True) == 0
    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_email("user@example.com")
        assert user is not None
        assert user.is_admin is True

    assert await set_admin_status("user@example.com", False) == 0
    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get_by_email("user@example.com")
        assert user is not None
        assert user.is_admin is False


@pytest.mark.asyncio
async def test_set_admin_status_reports_missing_user(capsys):
    assert await set_admin_status("missing@example.com", True) == 1

    captured = capsys.readouterr()
    assert "No user found for missing@example.com" in captured.err
