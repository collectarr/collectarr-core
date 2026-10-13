from __future__ import annotations

from typing import Any

from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.models.base import ItemKind


class MetadataCommonSupport:
    def _normalized_barcode_expr(self, column: Any) -> Any:
        from sqlalchemy import func

        return func.replace(func.replace(func.replace(column, "-", ""), " ", ""), ".", "")

    def _normalized_barcode(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().replace("-", "").replace(" ", "").replace(".", "")
        return normalized or None

    def _physical_format(
        self,
        metadata: dict | None,
        *,
        fallback_format: str | None,
        kind: ItemKind,
    ):
        config = None
        if isinstance(metadata, dict):
            normalized = metadata.get("normalized")
            if isinstance(normalized, dict) and normalized.get("physical_format"):
                config = physical_format_for_id(str(normalized["physical_format"]))
        if config is None and fallback_format and is_video_item_kind(kind):
            config = physical_format_for_id(fallback_format)
        return config
