from __future__ import annotations

from app.main import app


def test_tv_catalog_item_routes_are_mounted_without_old_graph_routes():
    paths = set(app.openapi()["paths"])
    required = {
        "/api/v1/metadata/tv/items",
        "/api/v1/metadata/tv/items/{item_id}",
    }

    assert required <= paths
    assert not any("/api/v1/metadata/tv/series/" in path for path in paths)
    assert not any("/api/v1/metadata/tv/releases/" in path for path in paths)
    assert not any("/api/v1/metadata/tv/seasons/" in path for path in paths)
