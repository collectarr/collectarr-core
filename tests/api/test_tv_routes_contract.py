from __future__ import annotations

from app.main import app


def test_unreleased_tv_routes_are_not_mounted():
    paths = set(app.openapi()["paths"])
    required = {
        "/api/v1/metadata/tv/items",
        "/api/v1/metadata/tv/items/{item_id}",
    }

    assert required.isdisjoint(paths)
    assert not any("/api/v1/metadata/tv/series/" in path for path in paths)
    assert not any("/api/v1/metadata/tv/releases/" in path for path in paths)
    assert not any("/api/v1/metadata/tv/seasons/" in path for path in paths)
