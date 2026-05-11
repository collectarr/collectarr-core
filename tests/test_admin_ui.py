import pytest


@pytest.mark.asyncio
async def test_admin_ui_is_served_without_api_token(client):
    response = await client.get("/admin/ui")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Collectarr Admin" in response.text
    assert "Personal library data stays local" in response.text
