from typing import Any, Mapping

from app.models.base import ItemKind
from app.providers.base import NormalizedItem, ProviderCapabilities, ProviderItem, ProviderSearchResult


class IGDBProvider:
    name = "igdb"
    capabilities = ProviderCapabilities(
        kind=ItemKind.game,
        display_name="IGDB",
        requires_user_key=True,
        requires_attribution=True,
        license_name="IGDB API Terms",
        terms_url="https://api-docs.igdb.com/",
        attribution_url="https://www.igdb.com/",
        cache_policy="Planned provider; respect IGDB commercial and attribution terms.",
    )

    @property
    def is_configured(self) -> bool:
        return False

    @property
    def status_message(self) -> str:
        return "IGDB live metadata is planned after the comics MVP."

    async def search(self, query: str) -> list[ProviderSearchResult]:
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id=f"stub-game-{query.lower().replace(' ', '-')}",
                title=f"{query} (IGDB stub)",
                kind=ItemKind.game,
            )
        ]

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        return ProviderItem(provider=self.name, provider_item_id=provider_item_id, raw={})

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        return NormalizedItem(
            kind=ItemKind.game,
            title=str(data.get("name") or "Unknown game"),
            synopsis=data.get("summary"),
            provider_ids={self.name: str(data.get("id"))} if data.get("id") else {},
        )
