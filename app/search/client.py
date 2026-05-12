from typing import Any

import meilisearch

from app.core.config import get_settings
from app.models.base import ItemKind


class SearchClient:
    index_name = "items"

    def __init__(self) -> None:
        settings = get_settings()
        self.client = meilisearch.Client(settings.meili_url, settings.meili_master_key)

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        year: int | None = None,
        barcode: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]] | None:
        try:
            filter_parts: list[str] = []
            if kind:
                filter_parts.append(f'kind = "{kind.value}"')
            if publisher:
                filter_parts.append(f'publisher = "{publisher}"')
            if year is not None:
                filter_parts.append(f"release_year = {year}")
            if barcode:
                normalized = barcode.strip().replace("-", "").replace(" ", "")
                filter_parts.append(f'barcodes = "{normalized}"')
            options: dict[str, Any] = {"limit": limit}
            filters = " AND ".join(filter_parts) if filter_parts else None
            if filters:
                options["filter"] = filters
            search_query = " ".join(
                part for part in (query, series, issue_number) if part and part.strip()
            )
            result = self.client.index(self.index_name).search(search_query, options)
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
        index.update_filterable_attributes(
            ["kind", "publisher", "region", "release_year", "barcodes"]
        )
        index.update_searchable_attributes(
            [
                "title",
                "item_number",
                "series_title",
                "volume_name",
                "publisher",
                "barcodes",
            ]
        )
