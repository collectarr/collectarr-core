from __future__ import annotations

import pytest

from app.main import app

SEARCH_PATHS = (
    "/api/v1/search",
    "/api/v1/metadata/anime/items",
    "/api/v1/metadata/boardgames/items",
    "/api/v1/metadata/books/items",
    "/api/v1/metadata/comics/items",
    "/api/v1/metadata/games/items",
    "/api/v1/metadata/manga/items",
    "/api/v1/metadata/movies/items",
    "/api/v1/metadata/music/items",
    "/api/v1/metadata/tv/items",
)


def test_catalog_search_routes_expose_a_page_contract() -> None:
    schema = app.openapi()
    components = schema["components"]["schemas"]
    for path in SEARCH_PATHS:
        response = schema["paths"][path]["get"]["responses"]["200"]
        body_schema = response["content"]["application/json"]["schema"]
        if "$ref" in body_schema:
            component_name = body_schema["$ref"].rsplit("/", 1)[-1]
            body_schema = components[component_name]

        assert set(body_schema["properties"]) == {
            "items",
            "next_offset",
            "has_more",
        }, path
        assert body_schema["properties"]["items"]["type"] == "array", path


@pytest.mark.asyncio
async def test_empty_shared_and_music_searches_return_empty_pages(client) -> None:
    shared = await client.get("/api/v1/search", params={"q": "missing"})
    music = await client.get("/api/v1/metadata/music/items", params={"q": "missing"})

    assert shared.status_code == 200
    assert shared.json() == {"items": [], "next_offset": None, "has_more": False}
    assert music.status_code == 200
    assert music.json() == {"items": [], "next_offset": None, "has_more": False}
