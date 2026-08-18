"""Metadata provider search support helpers."""

from __future__ import annotations

import logging
from typing import Any

from app.models.base import ExternalProvider, ItemKind
from app.providers.base import ProviderSearchResult

logger = logging.getLogger(__name__)


class MetadataProviderSearchSupport:
    """Provider search support (runtime migrated to app)."""

    def _provider_search_cache_key(
        self,
        provider_name: ExternalProvider | str,
        query: str,
        kind: ItemKind | None,
    ) -> tuple[str, str, str]:
        normalized_query = " ".join(query.split()).casefold()
        return self._provider_search_cache_namespace(provider_name), kind.value if kind else "*", normalized_query

    def _provider_search_cache_namespace(self, provider_name: ExternalProvider | str) -> str:
        return provider_name.value if isinstance(provider_name, ExternalProvider) else str(provider_name)

    def _clean_provider_query_part(self, value: str | None) -> str:
        if not value:
            return ""
        return " ".join(value.strip().split())

    def _clean_issue_number(self, value: str | None) -> str:
        if not value:
            return ""
        return value.strip().lstrip("#").strip()

    async def _cached_provider_search_results(
        self,
        cache_key: tuple[str, str, str],
    ) -> list[ProviderSearchResult] | None:
        return None

    async def _store_provider_search_results(
        self,
        cache_key: tuple[str, str, str],
        results: list[ProviderSearchResult],
    ) -> None:
        pass

    async def _with_stable_provider_image_urls(
        self,
        results: list[ProviderSearchResult],
    ) -> list[ProviderSearchResult]:
        return results
