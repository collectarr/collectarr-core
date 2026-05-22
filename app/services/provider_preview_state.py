from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from app.core.config import get_settings
from app.providers.base import NormalizedItem, ProviderItem


@dataclass(frozen=True)
class HydratedProviderPreview:
    provider_item: ProviderItem
    normalized: NormalizedItem


@dataclass(frozen=True)
class _ProviderPreviewCacheEntry:
    value: HydratedProviderPreview
    expires_at: datetime


_PROVIDER_PREVIEW_CACHE: Final[dict[tuple[str, str], _ProviderPreviewCacheEntry]] = {}


def clear_provider_preview_cache() -> None:
    _PROVIDER_PREVIEW_CACHE.clear()


class ProviderPreviewState:
    def __init__(self) -> None:
        self.settings = get_settings()

    def cached(self, provider: str, provider_item_id: str) -> HydratedProviderPreview | None:
        ttl = self.settings.provider_preview_cache_ttl_seconds
        if ttl <= 0:
            return None
        key = (provider, provider_item_id)
        entry = _PROVIDER_PREVIEW_CACHE.get(key)
        if entry is None:
            return None
        now = datetime.now(UTC)
        if entry.expires_at <= now:
            _PROVIDER_PREVIEW_CACHE.pop(key, None)
            return None
        return entry.value

    def store(
        self,
        provider: str,
        requested_provider_item_id: str,
        value: HydratedProviderPreview,
    ) -> None:
        ttl = self.settings.provider_preview_cache_ttl_seconds
        max_entries = self.settings.provider_preview_cache_max_entries
        if ttl <= 0 or max_entries <= 0:
            return
        self._evict_expired()
        entry = _ProviderPreviewCacheEntry(
            value=value,
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
        )
        keys = {
            (provider, requested_provider_item_id),
            (provider, value.provider_item.provider_item_id),
        }
        for key in keys:
            _PROVIDER_PREVIEW_CACHE[key] = entry
        while len(_PROVIDER_PREVIEW_CACHE) > max_entries:
            oldest_key = min(
                _PROVIDER_PREVIEW_CACHE,
                key=lambda item_key: _PROVIDER_PREVIEW_CACHE[item_key].expires_at,
            )
            _PROVIDER_PREVIEW_CACHE.pop(oldest_key, None)

    def _evict_expired(self) -> None:
        now = datetime.now(UTC)
        expired = [
            key for key, entry in _PROVIDER_PREVIEW_CACHE.items() if entry.expires_at <= now
        ]
        for key in expired:
            _PROVIDER_PREVIEW_CACHE.pop(key, None)