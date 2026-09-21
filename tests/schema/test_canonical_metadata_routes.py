from fastapi.routing import APIRoute

from app.main import app


def test_metadata_routes_use_typed_paths():
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert not any(path.startswith("/metadata/items") for path in paths)
