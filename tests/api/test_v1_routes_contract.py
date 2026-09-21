from fastapi.routing import APIRoute

from app.api.route_inventory import build_route_inventory
from app.api.v1 import API_V1_PREFIX
from app.main import app


def test_v1_composition_root_exposes_canonical_routes_and_explicit_aliases() -> None:
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert f"{API_V1_PREFIX}/health" in paths
    assert f"{API_V1_PREFIX}/auth/login" in paths
    assert f"{API_V1_PREFIX}/metadata/books/works/{{work_id}}" in paths
    assert f"{API_V1_PREFIX}/metadata/correction-proposals" in paths
    assert "/health" in paths
    assert "/auth/login" in paths
    assert "/metadata/books/works/{work_id}" in paths


def test_route_inventory_marks_only_existing_legacy_aliases() -> None:
    inventory = build_route_inventory(app.routes)

    health = next(item for item in inventory if item.canonical_path == "/api/v1/health")
    correction = next(
        item
        for item in inventory
        if item.canonical_path == "/api/v1/metadata/correction-proposals"
    )

    assert health.legacy_alias == "/health"
    assert correction.legacy_alias is None
