from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import MetadataProposal
from app.providers.registry import ProviderRegistry
from app.repositories.metadata import MetadataRepository
from app.schemas.metadata import (
    ItemResponse,
    MetadataProposalCreate,
    MetadataProposalResponse,
    ProviderSearchResultResponse,
    SearchResult,
    item_response_from_model,
)
from app.search.client import SearchClient


class MetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.metadata = MetadataRepository(db)
        self.search_client = SearchClient()
        self.providers = ProviderRegistry()

    async def get_item(self, item_id: UUID, kind: ItemKind) -> ItemResponse:
        item = await self.metadata.get_item(item_id, kind)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return item_response_from_model(item)

    async def search(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        year: int | None = None,
        barcode: str | None = None,
        limit: int = 25,
    ) -> list[SearchResult]:
        if not any(
            value is not None and str(value).strip()
            for value in (query, series, issue_number, publisher, year, barcode)
        ):
            return []

        meili_results = await self.search_client.search(
            query=query or "",
            kind=kind,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            year=year,
            barcode=barcode,
            limit=limit,
        )
        if meili_results is not None:
            return [SearchResult(**result) for result in meili_results]

        items = await self.metadata.search_items(
            query=query,
            kind=kind,
            limit=limit,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            year=year,
            barcode=barcode,
        )
        results: list[SearchResult] = []
        for item in items:
            cover_url = None
            thumbnail_url = None
            for edition in item.editions:
                primary = next(
                    (variant for variant in edition.variants if variant.is_primary), None
                )
                if primary:
                    cover_url = primary.cover_image_url
                    thumbnail_url = primary.thumbnail_image_url
                    break
            results.append(self._search_result(item, cover_url, thumbnail_url))
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

    async def search_provider(
        self,
        provider_name: ExternalProvider,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResultResponse]:
        provider = self.providers.maybe_get(provider_name)
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider '{provider_name.value}' is not configured",
            )
        if not provider.capabilities.supports_search:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider '{provider_name.value}' does not support search",
            )
        if kind is not None and provider.capabilities.kind != kind:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(f"Provider '{provider_name.value}' does not support kind '{kind.value}'"),
            )
        results = await provider.search(query)
        return [ProviderSearchResultResponse(**result.__dict__) for result in results]

    async def create_proposal(self, payload: MetadataProposalCreate) -> MetadataProposalResponse:
        proposal = MetadataProposal(
            provider=payload.provider,
            provider_item_id=payload.provider_item_id,
            query=payload.query,
            title=payload.title,
            summary=payload.summary,
            image_url=payload.image_url,
        )
        self.db.add(proposal)
        await self.db.commit()
        await self.db.refresh(proposal)
        return MetadataProposalResponse.model_validate(proposal)

    def _search_result(
        self, item, cover_url: str | None, thumbnail_url: str | None
    ) -> SearchResult:
        publisher = None
        release_date = None
        release_year = None
        barcode = None
        variant_name = None
        for edition in item.editions:
            publisher = publisher or edition.publisher
            barcode = barcode or edition.upc or edition.isbn
            if edition.release_date is not None and release_date is None:
                release_date = edition.release_date
                release_year = edition.release_date.year
            primary = next((variant for variant in edition.variants if variant.is_primary), None)
            if primary is not None and variant_name is None:
                variant_name = primary.name
                barcode = barcode or primary.barcode or primary.isbn
            if (
                publisher is not None
                and release_date is not None
                and barcode is not None
                and variant_name is not None
            ):
                break
        return SearchResult(
            id=item.id,
            kind=item.kind,
            title=item.title,
            item_number=item.item_number,
            synopsis=item.synopsis,
            cover_image_url=cover_url,
            thumbnail_image_url=thumbnail_url,
            publisher=publisher,
            release_date=release_date,
            release_year=release_year,
            barcode=barcode,
            variant=variant_name,
        )
