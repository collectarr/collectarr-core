from typing import Any, Mapping

from app.models.base import ItemKind
from app.providers.base import NormalizedItem, ProviderCapabilities, ProviderItem, ProviderSearchResult


class TMDbProvider:
    name = "tmdb"
    capabilities = ProviderCapabilities(
        kind=ItemKind.bluray,
        display_name="TMDb",
        requires_user_key=True,
        requires_attribution=True,
        allows_redistribution=False,
        license_name="TMDb API Terms",
        terms_url="https://www.themoviedb.org/documentation/api/terms-of-use",
        attribution_url="https://www.themoviedb.org/",
        cache_policy="Planned provider; commercial use may require a written agreement.",
    )

    @property
    def is_configured(self) -> bool:
        return False

    @property
    def status_message(self) -> str:
        return "TMDb live metadata is planned after the comics MVP."

    async def search(self, query: str) -> list[ProviderSearchResult]:
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id=f"stub-bluray-{query.lower().replace(' ', '-')}",
                title=f"{query} (TMDb stub)",
                kind=ItemKind.bluray,
            )
        ]

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        return ProviderItem(provider=self.name, provider_item_id=provider_item_id, raw={})

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        return NormalizedItem(
            kind=ItemKind.bluray,
            title=str(data.get("title") or data.get("name") or "Unknown title"),
            synopsis=data.get("overview"),
            provider_ids={self.name: str(data.get("id"))} if data.get("id") else {},
        )
