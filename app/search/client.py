import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import meilisearch

from app.core.config import get_settings
from app.models.base import ItemKind

logger = logging.getLogger(__name__)
T = TypeVar("T")


class SearchClient:
    index_name = "items"

    def __init__(self) -> None:
        settings = get_settings()
        self.client = meilisearch.Client(settings.meili_url, settings.meili_master_key)
        self.timeout_seconds = settings.meili_timeout_seconds

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        imprint: str | None = None,
        subtitle: str | None = None,
        series_group: str | None = None,
        language: str | None = None,
        country: str | None = None,
        age_rating: str | None = None,
        catalog_number: str | None = None,
        release_status: str | None = None,
        year: int | None = None,
        barcode: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]] | None:
        try:
            filter_parts: list[str] = []
            if kind:
                filter_parts.append(f"kind = {_meili_string(kind.value)}")
            if publisher:
                filter_parts.append(f"publisher = {_meili_string(publisher)}")
            if imprint:
                filter_parts.append(f"imprint = {_meili_string(imprint)}")
            if subtitle:
                filter_parts.append(f"subtitle = {_meili_string(subtitle)}")
            if series_group:
                filter_parts.append(f"series_group = {_meili_string(series_group)}")
            if language:
                filter_parts.append(f"language = {_meili_string(language)}")
            if country:
                filter_parts.append(f"region = {_meili_string(country)}")
            if age_rating:
                filter_parts.append(f"age_rating = {_meili_string(age_rating)}")
            if catalog_number:
                filter_parts.append(f"catalog_number = {_meili_string(catalog_number)}")
            if release_status:
                filter_parts.append(f"release_status = {_meili_string(release_status)}")
            if year is not None:
                filter_parts.append(f"release_year = {year}")
            if barcode:
                normalized = barcode.strip().replace("-", "").replace(" ", "")
                filter_parts.append(f"barcodes = {_meili_string(normalized)}")
            options: dict[str, Any] = {"limit": limit}
            filters = " AND ".join(filter_parts) if filter_parts else None
            if filters:
                options["filter"] = filters
            search_query = " ".join(
                part for part in (query, series, issue_number) if part and part.strip()
            )
            result = await self._run(
                lambda: self.client.index(self.index_name).search(search_query, options)
            )
        except Exception:
            logger.warning("meilisearch_search_failed", exc_info=True)
            return None
        return result.get("hits", [])

    async def index_documents(self, documents: list[dict[str, Any]]) -> None:
        if not documents:
            return
        await self._run(
            lambda: self.client.index(self.index_name).add_documents(
                documents,
                primary_key="id",
            )
        )

    async def replace_documents(self, documents: list[dict[str, Any]]) -> None:
        def replace() -> None:
            index = self.client.index(self.index_name)
            index.delete_all_documents()
            if documents:
                index.add_documents(documents, primary_key="id")

        await self._run(replace)

    async def replace_documents(self, documents: list[dict[str, Any]]) -> None:
        index = self.client.index(self.index_name)
        index.delete_all_documents()
        if documents:
            index.add_documents(documents, primary_key="id")

    async def index_documents_best_effort(self, documents: list[dict[str, Any]]) -> bool:
        try:
            await self.configure()
            await self.index_documents(documents)
        except Exception:
            return False
        return True

    async def configure(self) -> None:
        def configure() -> None:
            index = self.client.index(self.index_name)
            index.update_filterable_attributes(
                [
                    "kind",
                    "publisher",
                    "region",
                    "release_year",
                    "barcodes",
                    "series_title",
                    "release_status",
                    "language",
                    "imprint",
                    "series_group",
                    "age_rating",
                ]
            )
            index.update_searchable_attributes(
                [
                    "title",
                    "item_number",
                    "bundle_titles",
                    "series_title",
                    "volume_name",
                    "publisher",
                    "variant",
                    "variant_names",
                    "barcodes",
                    "bundle_release_ids",
                    "catalog_number",
                    "platforms",
                    "creators",
                    "characters",
                    "story_arcs",
                    "release_status",
                    "language",
                    "imprint",
                    "subtitle",
                    "series_group",
                    "age_rating",
                ]
            )
            index.update_displayed_attributes(
                [
                    "id",
                    "kind",
                    "title",
                    "item_number",
                    "runtime_minutes",
                    "cover_image_url",
                    "thumbnail_image_url",
                    "publisher",
                    "release_date",
                    "region",
                    "release_year",
                    "barcode",
                    "barcodes",
                    "catalog_number",
                    "variant",
                    "variant_names",
                    "bundle_titles",
                    "bundle_release_ids",
                    "series_title",
                    "volume_name",
                    "platforms",
                    "creators",
                    "characters",
                    "story_arcs",
                    "release_status",
                    "language",
                    "imprint",
                    "subtitle",
                    "series_group",
                    "age_rating",
                ]
            )
            index.update_sortable_attributes(
                ["title", "item_number", "release_year", "publisher"]
            )

        await self._run(configure)

    async def health(self) -> Any:
        return await self._run(self.client.health)

    async def _run(self, operation: Callable[[], T]) -> T:
        return await asyncio.wait_for(
            asyncio.to_thread(operation),
            timeout=self.timeout_seconds,
        )


def _meili_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
