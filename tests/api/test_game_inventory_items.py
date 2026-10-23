import json

import pytest

from app.db.session import AsyncSessionLocal
from app.services.catalog_game_hardware_items import CatalogGameHardwareItemService
from app.services.catalog_game_toy_items import CatalogGameToyItemService


@pytest.mark.db
@pytest.mark.asyncio
@pytest.mark.parametrize("service, kind, path, fields, forbidden", [
    (CatalogGameHardwareItemService, "game_hardware", "game-hardware",
     {"platform": "Pocket", "hardware_type": "Console"}, "toy_type"),
    (CatalogGameToyItemService, "game_toy", "game-toys",
     {"toy_type": "Figure", "toy_subtype": "Collectible"}, "hardware_type"),
])
async def test_independent_inventory_create_read_search_and_correction_schema(client, service, kind, path, fields, forbidden):
    async with AsyncSessionLocal() as db:
        item = await service(db).create_from_proposal({
            "title": "Isolated fixture", "barcode": "0000000000999",
            "release_date_parts": {"year": 2020}, **fields,
        })
        await db.commit()
    response = await client.get(f"/api/v1/metadata/{path}/items/{item.id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == kind
    assert body["release_date_parts"] == {"year": 2020}
    for key, value in fields.items():
        assert body[key] == value
    assert forbidden not in body
    for params in ({"q": "Isolated", "kind": kind}, {"barcode": "0000000000999", "kind": kind}):
        response = await client.get("/api/v1/search", params=params)
        assert response.status_code == 200, response.text
        hit = response.json()["items"][0]
        assert hit["id"] == str(item.id)
        assert hit["kind"] == kind
        for key, value in fields.items():
            assert hit["kind_data"][key] == value
    response = await client.get(f"/api/v1/metadata/{path}/items", params={"barcode": "0000000000999"})
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["id"] == str(item.id)
    response = await client.get(f"/api/v1/metadata/correction-targets/{kind}/{item.id}", params={"scope": "catalog_item"})
    assert response.status_code == 200, response.text
    assert forbidden not in response.json()["fields"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_hardware_search_filters_apply_before_pagination_and_reject_foreign_fields(client):
    async with AsyncSessionLocal() as db:
        service = CatalogGameHardwareItemService(db)
        for title, platform, hardware_type in [
            ("A fixture", "PC", "Console"),
            ("B fixture", "PC", "Controller"),
            ("C fixture", "Nintendo Switch", "Console"),
            ("D fixture", "PC", "Accessory"),
        ]:
            await service.create_from_proposal({"title": title, "platform": platform, "hardware_type": hardware_type})
        await db.commit()
    params = {"kind": "game_hardware", "field_filters": json.dumps({"platform": ["PC"], "hardware_type": ["Console", "Controller"]}), "limit": 1}
    first = await client.get("/api/v1/search", params=params)
    assert first.status_code == 200, first.text
    assert first.json()["items"][0]["kind_data"]["title"] == "A fixture"
    assert first.json()["has_more"] is True
    second = await client.get("/api/v1/search", params={**params, "offset": first.json()["next_offset"]})
    assert second.status_code == 200, second.text
    assert second.json()["items"][0]["kind_data"]["title"] == "B fixture"
    assert second.json()["has_more"] is False
    empty = await client.get("/api/v1/search", params={"kind": "game_hardware", "q": "fixture", "field_filters": json.dumps({"hardware_type": []})})
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    for kind, filters in [("game_toy", {"hardware_type": ["Console"]}), ("game_hardware", {"serial_number": ["personal"]}), (None, {"platform": ["PC"]})]:
        invalid = await client.get("/api/v1/search", params={"q": "fixture", **({"kind": kind} if kind else {}), "field_filters": json.dumps(filters)})
        assert invalid.status_code == 422, invalid.text
        assert invalid.json()["code"] == "invalid_catalog_filters"
