from __future__ import annotations

import logging

from app.core.config import get_settings
from app.models.base import ExternalProvider, ItemKind
from app.providers.registry import ProviderRegistry
from app.schemas import (
    MetadataProposalCreate,
    MetadataProposalResponse,
    ProviderSearchResultResponse,
    SeasonResponse,
)
from app.schemas.metadata_shared import SearchResult
from app.search.client import SearchClient
from app.services import metadata_public
from app.services.metadata_read_service import MetadataReadService
from app.services.metadata_search_service import MetadataSearchService
from app.services.provider_search_state import ProviderSearchState


class MetadataFacade:
    def __init__(self, db) -> None:
        self.db = db
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        self.search_client = SearchClient()
        self.providers = ProviderRegistry()
        self.provider_search_state = ProviderSearchState(self.settings)
        self.reads = MetadataReadService(self)
        self.search_service = MetadataSearchService(self)

    def __getattr__(self, name: str):
        return getattr(self.reads, name)

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

    async def barcode_provider_search(
        self,
        barcode: str,
        kind: ItemKind | None = None,
    ):
        return await metadata_public.barcode_provider_search(self, barcode, kind)

    async def search_provider(
        self,
        provider_name: ExternalProvider,
        query: str | None,
        kind: ItemKind | None = None,
        *,
        series: str | None = None,
        issue_number: str | None = None,
        year: int | None = None,
    ) -> list[ProviderSearchResultResponse]:
        return await metadata_public.search_provider(
            self,
            provider_name,
            query,
            kind,
            series=series,
            issue_number=issue_number,
            year=year,
        )

    async def search_default_provider(
        self,
        query: str | None,
        kind: ItemKind,
        *,
        series: str | None = None,
        issue_number: str | None = None,
        year: int | None = None,
    ) -> list[ProviderSearchResultResponse]:
        return await metadata_public.search_default_provider(
            self,
            query,
            kind,
            series=series,
            issue_number=issue_number,
            year=year,
        )

    async def mirror_provider_image_url(
        self,
        source_url: str | None,
        *,
        provider_name: str | ExternalProvider,
        provider_item_id: str | None,
        cache_only: bool = False,
    ) -> str | None:
        return await metadata_public.mirror_provider_image_url(
            self,
            source_url,
            provider_name=provider_name,
            provider_item_id=provider_item_id,
            cache_only=cache_only,
        )

    async def mirror_provider_image_bytes(
        self,
        image_bytes: bytes | None,
        *,
        source_url: str | None,
        provider_name: str | ExternalProvider,
        provider_item_id: str | None,
    ) -> str | None:
        return await metadata_public.mirror_provider_image_bytes(
            self,
            image_bytes,
            source_url=source_url,
            provider_name=provider_name,
            provider_item_id=provider_item_id,
        )

    async def create_proposal(self, payload: MetadataProposalCreate) -> MetadataProposalResponse:
        return await metadata_public.create_proposal(self, payload)

    async def get_provider_seasons(
        self,
        provider_name: ExternalProvider,
        provider_item_id: str,
    ) -> list[SeasonResponse]:
        return await metadata_public.get_provider_seasons(self, provider_name, provider_item_id)

    async def get_provider_volumes(
        self,
        provider_name: ExternalProvider,
        provider_item_id: str,
    ) -> list[SeasonResponse]:
        return await metadata_public.get_provider_volumes(self, provider_name, provider_item_id)

