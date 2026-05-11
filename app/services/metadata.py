from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import ItemKind
from app.repositories.metadata import MetadataRepository
from app.schemas.metadata import ItemResponse, SearchResult
from app.search.client import SearchClient


class MetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.metadata = MetadataRepository(db)
        self.search_client = SearchClient()

    async def get_item(self, item_id: UUID, kind: ItemKind) -> ItemResponse:
        item = await self.metadata.get_item(item_id, kind)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return ItemResponse.model_validate(item)

    async def search(self, query: str, kind: ItemKind | None = None) -> list[SearchResult]:
        if not query.strip():
            return []

        meili_results = await self.search_client.search(query=query, kind=kind)
        if meili_results:
            return [SearchResult(**result) for result in meili_results]

        items = await self.metadata.search_items(query=query, kind=kind)
        results: list[SearchResult] = []
        for item in items:
            cover_url = None
            thumbnail_url = None
            for edition in item.editions:
                primary = next((variant for variant in edition.variants if variant.is_primary), None)
                if primary:
                    cover_url = primary.cover_image_url
                    thumbnail_url = primary.thumbnail_image_url
                    break
            results.append(
                self._search_result(item, cover_url, thumbnail_url)
            )
        return results

    async def lookup_barcode(self, barcode: str, kind: ItemKind | None = None) -> SearchResult:
        item = await self.metadata.find_item_by_barcode(barcode, kind)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Barcode not found")

        cover_url = None
        thumbnail_url = None
        for edition in item.editions:
            primary = next((variant for variant in edition.variants if variant.is_primary), None)
            if primary:
                cover_url = primary.cover_image_url
                thumbnail_url = primary.thumbnail_image_url
                break
        return self._search_result(item, cover_url, thumbnail_url)

    def _search_result(
        self, item, cover_url: str | None, thumbnail_url: str | None
    ) -> SearchResult:
        return SearchResult(
            id=item.id,
            kind=item.kind,
            title=item.title,
            item_number=item.item_number,
            synopsis=item.synopsis,
            cover_image_url=cover_url,
            thumbnail_image_url=thumbnail_url,
        )
