"""Strict toys-to-life response, independent of the Game response."""

from typing import Any, Literal

from pydantic import ConfigDict

from app.schemas.catalog_item_base import CatalogItemBaseResponse


class CatalogGameToyItemResponse(CatalogItemBaseResponse):
    kind: Literal["game_toy"] = "game_toy"
    sort_key: str | None = None
    barcode: str | None = None
    release_date_parts: dict[str, int] | None = None
    series_title: str | None = None
    toy_type: str | None = None
    toy_subtype: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    external_links: list[dict[str, Any]] | None = None
    trailer_urls: list[dict[str, Any]] | None = None
    model_config = ConfigDict(extra="forbid")
