"""Provider registry descriptor metadata."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.base import ExternalProvider, ItemKind


@dataclass(frozen=True)
class ProviderRegistryStatus:
    name: str
    display_name: str
    kind: ItemKind
    supported_kinds: tuple[ItemKind, ...]
    is_configured: bool
    status_message: str
    supports_search: bool = False
    supports_ingest: bool = False
    requires_user_key: bool = False
    non_commercial_only: bool = False
    allows_redistribution: bool = False
    allows_image_mirroring: bool = False
    image_policy: str = "direct"
    requires_attribution: bool = False
    license_name: str | None = None
    terms_url: str | None = None
    attribution_url: str | None = None
    rate_limit: str | None = None
    cache_policy: str | None = None


class ProviderRegistry:
    """Core lightweight provider metadata descriptor registry (runtime in App)."""

    def __init__(self) -> None:
        pass

    def get(self, name: str | ExternalProvider) -> Any | None:
        return None

    def maybe_get(self, name: str | ExternalProvider) -> Any | None:
        return None

    def all(self) -> list[Any]:
        return []

    def status_entries(self) -> list[ProviderRegistryStatus]:
        return []

    def status_entries_for_settings(self, settings: Any) -> list[ProviderRegistryStatus]:
        return []
