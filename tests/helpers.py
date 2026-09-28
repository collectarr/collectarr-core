from app.db.session import AsyncSessionLocal


async def register_and_login(client) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123", "display_name": "Test"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]
