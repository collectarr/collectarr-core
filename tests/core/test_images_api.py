import base64
from uuid import uuid4

import pytest

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
