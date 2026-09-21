from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def test_tv_routes_contract_paths_exist():
    paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
    }
    required = {
        "/api/v1/metadata/tv/seasons/{season_id}",
        "/api/v1/metadata/tv/seasons/{season_id}/episodes",
        "/api/v1/metadata/tv/series/{series_id}/releases",
        "/api/v1/metadata/tv/releases/{release_id}",
        "/api/v1/metadata/tv/releases/{release_id}/media",
        "/api/v1/metadata/tv/releases/{release_id}/episode-map",
        "/api/v1/metadata/tv/media/{media_id}",
    }

    assert required <= paths
