from typing import Any, Mapping

from app.models.base import ItemKind
from app.providers.base import NormalizedItem, ProviderItem, ProviderSearchResult


class ComicVineProvider:
    name = "comicvine"

    async def search(self, query: str) -> list[ProviderSearchResult]:
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id=f"stub-comic-{query.lower().replace(' ', '-')}",
                title=f"{query} (ComicVine stub)",
                kind=ItemKind.comic,
                summary="Stub result. Add ComicVine API credentials to enable live metadata.",
            )
        ]

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        return ProviderItem(provider=self.name, provider_item_id=provider_item_id, raw={})

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        return NormalizedItem(
            kind=ItemKind.comic,
            title=str(data.get("name") or data.get("title") or "Unknown comic"),
            item_number=str(data.get("issue_number")) if data.get("issue_number") else None,
            synopsis=data.get("description"),
            provider_ids={self.name: str(data.get("id"))} if data.get("id") else {},
        )

