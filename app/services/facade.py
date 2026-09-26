from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult
from app.search.client import SearchClient
from app.services.metadata.metadata_read_service import MetadataReadService
from app.services.metadata.metadata_search_service import MetadataSearchService


class MetadataFacade(MetadataReadService):
    """Typed catalog reads, source-neutral search, and image/cache access."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.search_client = SearchClient()
        self.search_service = MetadataSearchService(self)

    async def search(
        self,
        query: str | None = None,
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
    ) -> list[SearchResult]:
        return await self.search_service.search(
            query=query,
            kind=kind,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            imprint=imprint,
            subtitle=subtitle,
            series_group=series_group,
            language=language,
            country=country,
            age_rating=age_rating,
            catalog_number=catalog_number,
            release_status=release_status,
            year=year,
            barcode=barcode,
            limit=limit,
        )

    async def lookup_barcode(self, barcode: str, kind: ItemKind | None = None) -> SearchResult:
        return await self.search_service.lookup_barcode(barcode, kind)
