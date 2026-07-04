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
        "/metadata/tv/seasons/{season_id}",
        "/metadata/tv/seasons/{season_id}/episodes",
        "/metadata/tv/series/{series_id}/releases",
        "/metadata/tv/releases/{release_id}",
        "/metadata/tv/releases/{release_id}/media",
        "/metadata/tv/releases/{release_id}/episode-map",
        "/metadata/tv/media/{media_id}",
    }

    assert required <= paths
