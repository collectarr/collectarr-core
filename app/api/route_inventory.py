from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from app.api.v1 import API_V1_PREFIX


@dataclass(frozen=True)
class RouteInventoryEntry:
    method: str
    canonical_path: str
    legacy_alias: str | None
    name: str


def build_route_inventory(routes: Iterable[BaseRoute]) -> tuple[RouteInventoryEntry, ...]:
    """Inventory versioned routes and identify their explicit aliases."""

    api_routes = [route for route in routes if isinstance(route, APIRoute)]
    paths = {route.path for route in api_routes}
    entries: list[RouteInventoryEntry] = []
    for route in api_routes:
        if not route.path.startswith(f"{API_V1_PREFIX}/"):
            continue
        relative_path = route.path[len(API_V1_PREFIX) :]
        legacy_alias = relative_path if relative_path in paths else None
        for method in sorted(route.methods or ()):
            entries.append(
                RouteInventoryEntry(
                    method=method,
                    canonical_path=route.path,
                    legacy_alias=legacy_alias,
                    name=route.name,
                )
            )
    return tuple(sorted(entries, key=lambda item: (item.canonical_path, item.method)))
