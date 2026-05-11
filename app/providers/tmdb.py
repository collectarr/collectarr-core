from typing import Any, Mapping

from app.models.base import ItemKind
from app.providers.base import NormalizedItem, ProviderItem, ProviderSearchResult


class TMDbProvider:
    name = "tmdb"

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

