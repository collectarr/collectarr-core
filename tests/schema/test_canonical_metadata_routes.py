from fastapi.routing import APIRoute

from app.main import app


def test_catalog_metadata_api_exposes_only_catalog_item_roots():
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    metadata_paths = {path for path in paths if path.startswith("/api/v1/metadata/")}

    assert "/api/v1/metadata/catalog-items" in metadata_paths
    assert "/api/v1/metadata/catalog-items/{item_id}" in metadata_paths
    assert not any(path.startswith("/metadata/items") for path in paths)
    assert not any("/works" in path or "/releases" in path for path in metadata_paths)
