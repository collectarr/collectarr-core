from fastapi.routing import APIRoute

from app.main import app


def test_no_metadata_items_routes():
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert not any(path.startswith("/metadata/items") for path in paths)
