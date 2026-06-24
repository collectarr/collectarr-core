from collections.abc import Mapping
from typing import Any

from app.models.base import ExternalProvider, ItemKind
from app.providers.base import (
    NormalizedItem,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)


class PlannedProvider:
    def __init__(
        self,
        provider: ExternalProvider,
        kind: ItemKind,
        display_name: str,
        *,
        requires_user_key: bool = False,
        requires_attribution: bool = True,
        allows_redistribution: bool = False,
        allows_image_mirroring: bool = False,
        license_name: str | None = None,
        terms_url: str | None = None,
        attribution_url: str | None = None,
        cache_policy: str | None = None,
    ) -> None:
        self.provider = provider
        self.name = provider.value
        self.capabilities = ProviderCapabilities(
            kind=kind,
            display_name=display_name,
            supports_search=True,
            supports_ingest=False,
            requires_user_key=requires_user_key,
            requires_attribution=requires_attribution,
            allows_redistribution=allows_redistribution,
            allows_image_mirroring=allows_image_mirroring,
            license_name=license_name,
            terms_url=terms_url,
            attribution_url=attribution_url,
            cache_policy=cache_policy
            or f"Planned {display_name} provider; do not ingest into the catalog yet.",
        )

    @property
    def is_configured(self) -> bool:
        return False

    @property
    def status_message(self) -> str:
        return (
            f"{self.capabilities.display_name} search is scaffolded; "
            "catalog ingest is not implemented yet."
        )

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []
        result_kind = (
            kind if kind and self.capabilities.supports_kind(kind) else self.capabilities.kind
        )
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id=(f"stub-{result_kind.value}-{self._slug(normalized_query)}"),
                title=f"{normalized_query} ({self.capabilities.display_name} stub)",
                kind=result_kind,
                summary=(
                    f"{self.capabilities.display_name} live normalization is planned; "
                    "this result is search-only."
                ),
            )
        ]

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        raise NotImplementedError(
            f"{self.capabilities.display_name} catalog ingest is not implemented"
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        raise NotImplementedError(
            f"{self.capabilities.display_name} catalog ingest is not implemented"
        )

    def _slug(self, value: str) -> str:
        return "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())
