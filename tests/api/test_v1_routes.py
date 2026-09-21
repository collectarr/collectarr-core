from fastapi.routing import APIRoute

from app.api.v1 import API_V1_PREFIX
from app.main import app


def test_v1_composition_root_exposes_canonical_routes() -> None:
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert f"{API_V1_PREFIX}/health" in paths
    assert f"{API_V1_PREFIX}/auth/login" in paths
    assert f"{API_V1_PREFIX}/metadata/books/works/{{work_id}}" in paths
    assert f"{API_V1_PREFIX}/metadata/correction-targets/{{kind}}/{{entity_id}}" in paths
    assert f"{API_V1_PREFIX}/metadata/correction-proposals" in paths
    assert f"{API_V1_PREFIX}/metadata/correction-proposals/{{proposal_id}}/approve" in paths
