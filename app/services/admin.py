from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canonical import Edition, ExternalProviderId, Item
from app.models.base import ExternalProvider
from app.providers.registry import ProviderRegistry
from app.repositories.metadata import MetadataRepository
from app.schemas.admin import ProviderIngestRequest, ProviderIngestResponse, ProviderSearchRequest
from app.schemas.metadata import ItemResponse


class AdminMetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.providers = ProviderRegistry()

    async def provider_search(self, payload: ProviderSearchRequest) -> list[dict[str, Any]]:
        provider = self.providers.get(payload.provider)
        results = await provider.search(payload.query)
        return [result.__dict__ for result in results]

    async def ingest(self, payload: ProviderIngestRequest) -> ProviderIngestResponse:
        provider = self.providers.get(payload.provider)
        existing_provider_id = await self._get_provider_id(payload)
        if existing_provider_id:
            item = await MetadataRepository(self.db).get_item(existing_provider_id.entity_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider link is stale")
            return ProviderIngestResponse(
                item_id=item.id,
                created=False,
                item=ItemResponse.model_validate(item),
            )

        provider_item = await provider.get_item(payload.provider_item_id)
        normalized = await provider.normalize(provider_item.raw | {"id": payload.provider_item_id})
        item = Item(
            kind=normalized.kind,
            title=normalized.title,
            item_number=normalized.item_number,
            sort_key=f"{normalized.title.lower()}-{normalized.item_number or ''}".strip("-"),
            synopsis=normalized.synopsis,
        )
        edition = Edition(
            item=item,
            title=normalized.edition_title or "Standard Edition",
            metadata_json={"provider": payload.provider, "provider_item_id": payload.provider_item_id},
        )
        self.db.add_all([item, edition])
        await self.db.flush()
        self.db.add(
            ExternalProviderId(
                provider=ExternalProvider(payload.provider),
                provider_item_id=payload.provider_item_id,
                entity_type="item",
                entity_id=item.id,
            )
        )
        await self.db.commit()
        loaded_item = await MetadataRepository(self.db).get_item(item.id)
        return ProviderIngestResponse(
            item_id=item.id,
            created=True,
            item=ItemResponse.model_validate(loaded_item),
        )

    async def _get_provider_id(self, payload: ProviderIngestRequest) -> ExternalProviderId | None:
        result = await self.db.execute(
            select(ExternalProviderId).where(
                ExternalProviderId.provider == ExternalProvider(payload.provider),
                ExternalProviderId.provider_item_id == payload.provider_item_id,
            )
        )
        return result.scalar_one_or_none()
