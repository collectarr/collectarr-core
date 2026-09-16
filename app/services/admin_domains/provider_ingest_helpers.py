from __future__ import annotations

import re
from typing import Any

from app.catalog.physical_formats import (
    PhysicalFormatConfig,
    is_video_item_kind,
    physical_format_for_id,
)
from app.providers.base import NormalizedVariantCover

_LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")
_REGION_RE = re.compile(r"^[A-Z]{2}(?:-[A-Z0-9]{1,3})?$")


def physical_format_for_normalized(normalized: Any) -> PhysicalFormatConfig | None:
    if not is_video_item_kind(normalized.kind):
        return None
    candidate = normalized.physical_format or normalized.edition_format
    if not candidate:
        return None
    return physical_format_for_id(candidate)


def variant_cover_name(cover: NormalizedVariantCover, index: int) -> str:
    name = cover.name.strip() if cover.name else ""
    return name[:255] if name else f"Variant cover {index}"


def cover_metadata(
    source_url: str | None,
    mirrored_cover: Any | None,
) -> dict[str, Any]:
    if mirrored_cover is not None:
        return {
            "cover_status": "mirrored",
            "cover_source_url": source_url,
            "cover_delivery_url": mirrored_cover.url,
            "cover_storage": "object_storage",
            "cover_policy": "minio_mirror",
        }
    if source_url:
        return {
            "cover_status": "external_url",
            "cover_source_url": source_url,
            "cover_delivery_url": source_url,
            "cover_storage": "provider_external_url",
            "cover_policy": "external_url_default",
        }
    return {
        "cover_status": "missing",
        "cover_source_url": None,
        "cover_delivery_url": None,
        "cover_storage": "generated_client_fallback",
        "cover_policy": "generated_cover_fallback",
    }


def normalized_release_status(value: str | None) -> str | None:
    text = " ".join(str(value or "").split()).strip().lower()
    return text or None


def normalized_language(value: str | None) -> str | None:
    text = " ".join(str(value or "").split()).strip().lower()
    if not text:
        return None
    return text if _LANGUAGE_RE.match(text) else None


def normalized_region(value: str | None) -> str | None:
    text = " ".join(str(value or "").split()).strip().upper()
    if not text:
        return None
    return text if _REGION_RE.match(text) else None


def comic_identifier_type(base_type: str, value: str) -> str:
    return book_identifier_type(base_type, value)


def book_identifier_type(base_type: str, value: str) -> str:
    normalized = normalized_identifier(value)
    if base_type == "isbn":
        if len(normalized) == 10:
            return "isbn10"
        if len(normalized) == 13:
            return "isbn13"
        return "isbn13"
    if base_type == "upc":
        if len(normalized) == 13:
            return "ean"
        return "upc"
    return base_type


def normalized_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())
