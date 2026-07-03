from __future__ import annotations

import logging
import re
from dataclasses import replace
from urllib.parse import urlparse

from app.models import ExternalProvider
from app.providers.base import MetadataProvider, ProviderSearchResult

logger = logging.getLogger(__name__)
_UPSTREAM_HTTP_STATUS_RE = re.compile(r"\bHTTP\s+(?P<status>\d{3})\b")


class ImageService:
    async def mirror_provider_image_url(
        self,
        source_url: str | None,
        *,
        provider_name: str | ExternalProvider,
        provider_item_id: str | None,
        cache_only: bool = False,
    ) -> str | None:
        from app.services.metadata_public import mirror_provider_image_url as _mirror_provider_image_url

        return await _mirror_provider_image_url(
            self,
            source_url,
            provider_name=provider_name,
            provider_item_id=provider_item_id,
            cache_only=cache_only,
        )

    async def mirror_provider_image_bytes(
        self,
        image_bytes: bytes | None,
        *,
        source_url: str | None,
        provider_name: str | ExternalProvider,
        provider_item_id: str | None,
    ) -> str | None:
        from app.services.metadata_public import mirror_provider_image_bytes as _mirror_provider_image_bytes

        return await _mirror_provider_image_bytes(
            self,
            image_bytes,
            source_url=source_url,
            provider_name=provider_name,
            provider_item_id=provider_item_id,
        )

    async def _with_stable_provider_image_urls(
        self,
        results: list[ProviderSearchResult],
    ) -> list[ProviderSearchResult]:
        stable_results: list[ProviderSearchResult] = []
        for result in results:
            mirrored_url = await self.mirror_provider_image_url(
                result.image_url,
                provider_name=result.provider,
                provider_item_id=result.provider_item_id,
                cache_only=True,
            )
            stable_results.append(replace(result, image_url=mirrored_url) if mirrored_url else result)
        return stable_results

    def _can_mirror_provider_image(
        self,
        provider_name: str | ExternalProvider,
        source_url: str | None,
    ) -> bool:
        if not self.settings.mirror_provider_images:
            return False
        if not self._is_external_image_url(source_url):
            return False
        provider = self._provider_for_name(provider_name)
        if provider is None:
            return False
        if self.settings.mirror_provider_images_allow_restricted:
            return True
        return provider.capabilities.allows_image_mirroring

    def _provider_for_name(
        self,
        provider_name: str | ExternalProvider,
    ) -> MetadataProvider | None:
        try:
            provider_enum = provider_name if isinstance(provider_name, ExternalProvider) else ExternalProvider(str(provider_name))
        except ValueError:
            return None
        return self.providers.maybe_get(provider_enum)

    def _provider_value(self, provider_name: str | ExternalProvider) -> str:
        return provider_name.value if isinstance(provider_name, ExternalProvider) else str(provider_name)

    def _is_external_image_url(self, value: str | None) -> bool:
        if not value:
            return False
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
