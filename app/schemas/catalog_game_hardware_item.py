"""Strict Hardware response; no game progress or per-device serial number."""

from typing import Any, Literal

from pydantic import ConfigDict

from app.schemas.catalog_item_base import CatalogItemBaseResponse


class CatalogGameHardwareItemResponse(CatalogItemBaseResponse):
    kind: Literal["game_hardware"] = "game_hardware"
    sort_key: str | None = None
    platform: str | None = None
    hardware_type: str | None = None
    barcode: str | None = None
    release_date_parts: dict[str, int] | None = None
    series_title: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    external_links: list[dict[str, Any]] | None = None
    trailer_urls: list[dict[str, Any]] | None = None
    model_config = ConfigDict(extra="forbid")
