from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    Edition,
    ExternalProviderId,
    Item,
    MetadataProposal,
    Release,
    Series,
    Variant,
    Volume,
)
from app.providers.base import MetadataProvider
from app.providers.registry import ProviderRegistry
from app.repositories.metadata import MetadataRepository
from app.schemas.admin import (
    ProviderIngestRequest,
    ProviderIngestResponse,
    MetadataProposalAdminResponse,
    ProviderSearchRequest,
    ProviderStatusResponse,
)
from app.schemas.metadata import ItemResponse
from app.search.client import SearchClient
from app.search.documents import item_search_document
from app.storage.images import ImageMirror


class AdminMetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.providers = ProviderRegistry()
        self.settings = get_settings()

    async def provider_statuses(self) -> list[ProviderStatusResponse]:
        return [
            ProviderStatusResponse(
                name="comicvine",
                kind=ItemKind.comic.value,
                status="live" if self.settings.comicvine_api_key else "stub",
                is_configured=bool(self.settings.comicvine_api_key),
                message=(
                    "ComicVine API key configured."
                    if self.settings.comicvine_api_key
                    else "Set COMICVINE_API_KEY to enable live ComicVine metadata."
                ),
            ),
            ProviderStatusResponse(
                name="igdb",
                kind=ItemKind.game.value,
                status="stub",
                is_configured=False,
                message="IGDB live metadata is planned after the comics MVP.",
            ),
            ProviderStatusResponse(
                name="tmdb",
                kind=ItemKind.bluray.value,
                status="stub",
                is_configured=False,
                message="TMDb live metadata is planned after the comics MVP.",
            ),
        ]

    async def provider_search(self, payload: ProviderSearchRequest) -> list[dict[str, Any]]:
        provider = self._provider(payload.provider)
        results = await provider.search(payload.query)
        return [result.__dict__ for result in results]

    async def list_proposals(
        self, status_filter: str = "pending"
    ) -> list[MetadataProposalAdminResponse]:
        result = await self.db.execute(
            select(MetadataProposal)
            .where(MetadataProposal.status == status_filter)
            .order_by(MetadataProposal.created_at.asc())
        )
        return [
            MetadataProposalAdminResponse.model_validate(proposal) for proposal in result.scalars()
        ]

    async def approve_proposal(self, proposal_id: UUID) -> ProviderIngestResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
        if proposal.provider_item_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Proposal does not have a provider item id",
            )
        response = await self.ingest(
            ProviderIngestRequest(
                provider=proposal.provider,
                provider_item_id=proposal.provider_item_id,
            )
        )
        proposal.status = "approved"
        await self.db.commit()
        return response

    async def reject_proposal(self, proposal_id: UUID) -> MetadataProposalAdminResponse:
        proposal = await self.db.get(MetadataProposal, proposal_id)
        if proposal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
        proposal.status = "rejected"
        await self.db.commit()
        await self.db.refresh(proposal)
        return MetadataProposalAdminResponse.model_validate(proposal)

    async def ingest(self, payload: ProviderIngestRequest) -> ProviderIngestResponse:
        provider = self._provider(payload.provider)
        existing_provider_id = await self._get_provider_id(payload)
        if existing_provider_id:
            return await self._existing_response(existing_provider_id)

        provider_item = await provider.get_item(payload.provider_item_id)
        existing_provider_id = await self._get_provider_id_value(
            payload.provider, provider_item.provider_item_id
        )
        if existing_provider_id:
            return await self._existing_response(existing_provider_id)

        normalized = await provider.normalize(
            dict(provider_item.raw) | {"id": provider_item.provider_item_id}
        )
        volume = await self._upsert_volume(
            normalized.kind,
            normalized.series_title,
            normalized.volume_name,
            normalized.volume_start_year,
        )
        item = Item(
            volume=volume,
            kind=normalized.kind,
            title=normalized.title,
            item_number=normalized.item_number,
            sort_key=self._sort_key(normalized.kind, normalized.title, normalized.item_number),
            synopsis=normalized.synopsis,
        )
        edition = Edition(
            item=item,
            title=normalized.edition_title or "Standard Edition",
            format=normalized.edition_format,
            publisher=normalized.publisher,
            release_date=normalized.release_date,
            metadata_json={
                "provider": payload.provider.value,
                "provider_item_id": provider_item.provider_item_id,
                "source": provider_item.raw,
            },
        )
        mirrored_cover = await ImageMirror().mirror_cover_best_effort(
            normalized.cover_image_url,
            payload.provider.value,
            provider_item.provider_item_id,
        )
        variant = Variant(
            edition=edition,
            name="Cover A",
            cover_image_key=mirrored_cover.key if mirrored_cover else None,
            cover_image_url=mirrored_cover.url if mirrored_cover else normalized.cover_image_url,
            thumbnail_image_key=mirrored_cover.thumbnail_key if mirrored_cover else None,
            thumbnail_image_url=mirrored_cover.thumbnail_url if mirrored_cover else None,
            is_primary=True,
        )
        release = Release(
            edition=edition,
            region="US",
            release_date=normalized.release_date,
            publisher=normalized.publisher,
            external_ids=normalized.provider_ids,
        )
        self.db.add_all([item, edition, variant, release])
        await self.db.flush()
        self._add_provider_links(payload.provider, normalized.provider_ids, "item", item.id)
        if volume:
            self._add_provider_links(
                payload.provider, normalized.volume_provider_ids, "volume", volume.id
            )
        await self.db.commit()
        loaded_item = await MetadataRepository(self.db).get_item(item.id)
        if loaded_item:
            await SearchClient().index_documents_best_effort([item_search_document(loaded_item)])
        return ProviderIngestResponse(
            item_id=item.id,
            created=True,
            item=ItemResponse.model_validate(loaded_item),
        )

    def _provider(self, provider: ExternalProvider) -> MetadataProvider:
        try:
            return self.providers.get(provider.value)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider '{provider.value}' is not configured",
            ) from exc

    async def _get_provider_id(self, payload: ProviderIngestRequest) -> ExternalProviderId | None:
        return await self._get_provider_id_value(payload.provider, payload.provider_item_id)

    async def _get_provider_id_value(
        self, provider: ExternalProvider, provider_item_id: str
    ) -> ExternalProviderId | None:
        result = await self.db.execute(
            select(ExternalProviderId).where(
                ExternalProviderId.provider == provider,
                ExternalProviderId.provider_item_id == provider_item_id,
            )
        )
        return result.scalar_one_or_none()

    async def _existing_response(self, provider_id: ExternalProviderId) -> ProviderIngestResponse:
        item = await MetadataRepository(self.db).get_item(provider_id.entity_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Provider link is stale"
            )
        return ProviderIngestResponse(
            item_id=item.id,
            created=False,
            item=ItemResponse.model_validate(item),
        )

    async def _upsert_volume(
        self,
        kind: ItemKind,
        series_title: str | None,
        volume_name: str | None,
        volume_start_year: int | None,
    ) -> Volume | None:
        if not series_title and not volume_name:
            return None

        title = series_title or volume_name or "Unknown Series"
        series = await self._get_or_create_series(kind, title)
        name = volume_name or title
        result = await self.db.execute(
            select(Volume).where(Volume.series_id == series.id, Volume.name == name)
        )
        volume = result.scalar_one_or_none()
        if volume is None:
            volume = Volume(series=series, name=name, start_year=volume_start_year)
            self.db.add(volume)
            await self.db.flush()
        elif volume.start_year is None and volume_start_year:
            volume.start_year = volume_start_year
        return volume

    async def _get_or_create_series(self, kind: ItemKind, title: str) -> Series:
        result = await self.db.execute(
            select(Series).where(Series.kind == kind, Series.title == title)
        )
        series = result.scalar_one_or_none()
        if series is None:
            series = Series(kind=kind, title=title, slug=self._slug(title))
            self.db.add(series)
            await self.db.flush()
        return series

    def _add_provider_links(
        self,
        provider: ExternalProvider,
        provider_ids: dict[str, str],
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        provider_id = provider_ids.get(provider.value)
        if not provider_id:
            return
        self.db.add(
            ExternalProviderId(
                provider=provider,
                provider_item_id=provider_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )

    def _sort_key(self, kind: ItemKind, title: str, item_number: str | None) -> str:
        if kind == ItemKind.comic and item_number:
            return f"{self._slug(title)}-{item_number.zfill(6)}"
        return f"{self._slug(title)}-{item_number or ''}".strip("-")

    def _slug(self, value: str) -> str:
        return "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())
