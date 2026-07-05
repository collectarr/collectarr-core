from __future__ import annotations

import logging
from collections.abc import Iterable

from app.core.config import get_settings

logger = logging.getLogger(__name__)

INTERNAL_BOOKKEEPING_KEYS = {
    "format_templateimage",
    "format_scaledimage",
    "country_scaledimage",
    "language_scaledimage",
    "audiencerating_templateimage",
    "region_scaledimage",
    "audio_templateimage",
    "physical_format_label",
    "physical_format_media_family",
    "physical_format_variant_type",
    "associated_image_id",
    "cover_delivery_url",
    "cover_policy",
    "cover_source_url",
    "cover_status",
    "cover_storage",
}

LEGACY_PROJECTION_KEYS = {
    "cover_image_url",
    "thumbnail_image_url",
    "synopsis",
    "crossover",
    "plot_summary",
    "plot_description",
    "series_tags",
}

_WARNED_SOURCES: set[str] = set()


def is_legacy_projection_key(key: str) -> bool:
    return key in INTERNAL_BOOKKEEPING_KEYS or key in LEGACY_PROJECTION_KEYS


def warn_if_legacy_projection_used(source: str, keys: Iterable[str]) -> None:
    settings = get_settings()
    if settings.environment not in {"development", "test"}:
        return
    legacy_keys = sorted({key for key in keys if is_legacy_projection_key(key)})
    if not legacy_keys or source in _WARNED_SOURCES:
        return
    _WARNED_SOURCES.add(source)
    logger.warning(
        "legacy projection is still active in %s; move keys to typed readers and delete this compatibility layer: %s",
        source,
        ", ".join(legacy_keys),
    )

