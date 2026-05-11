from typing import Any

import meilisearch

from app.core.config import get_settings
from app.models.base import ItemKind


class SearchClient:
    index_name = "items"

    def __init__(self) -> None:
        settings = get_settings()
        self.client = meilisearch.Client(settings.meili_url, settings.meili_master_key)

    async def search(self, query: str, kind: ItemKind | None = None) -> list[dict[str, Any]] | None:
        try:
            filters = f'kind = "{kind.value}"' if kind else None
            options: dict[str, Any] = {"limit": 25}
            if filters:
                options["filter"] = filters
            result = self.client.index(self.index_name).search(query, options)
        except Exception:
            return None
        return result.get("hits", [])

    async def index_documents(self, documents: list[dict[str, Any]]) -> None:
        if not documents:
            return
        self.client.index(self.index_name).add_documents(documents, primary_key="id")

    async def index_documents_best_effort(self, documents: list[dict[str, Any]]) -> bool:
        try:
            await self.configure()
            await self.index_documents(documents)
        except Exception:
            return False
        return True

    async def configure(self) -> None:
        index = self.client.index(self.index_name)
        index.update_filterable_attributes(["kind", "publisher", "region"])
        index.update_searchable_attributes(
            ["title", "item_number", "synopsis", "series_title", "volume_name"]
        )
