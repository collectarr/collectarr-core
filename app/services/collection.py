from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import SyncAction
from app.models.sync import SyncChange
from app.models.user import OwnedItem, User
from app.repositories.collection import CollectionRepository
from app.repositories.metadata import MetadataRepository
from app.repositories.sync import SyncRepository
from app.schemas.collection import CollectionAddRequest, CollectionPatchRequest, OwnedItemResponse


class CollectionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.collection = CollectionRepository(db)
        self.metadata = MetadataRepository(db)
        self.sync = SyncRepository(db)

    async def list_owned(self, user: User) -> list[OwnedItemResponse]:
        items = await self.collection.list_owned(user.id)
        return [OwnedItemResponse.model_validate(item) for item in items]

    async def add_owned(self, user: User, payload: CollectionAddRequest) -> OwnedItemResponse:
        try:
            await self.metadata.validate_refs(payload.item_id, payload.edition_id, payload.variant_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        collection_id = payload.collection_id or await self.collection.default_collection_id(user.id)
        owned_item = OwnedItem(
            user_id=user.id,
            collection_id=collection_id,
            item_id=payload.item_id,
            edition_id=payload.edition_id,
            variant_id=payload.variant_id,
            condition=payload.condition,
            grade=payload.grade,
            personal_notes=payload.personal_notes,
            client_updated_at=payload.client_updated_at,
        )
        await self.collection.add(owned_item)
        await self._record_owned_change(user.id, owned_item, SyncAction.upsert)
        await self.db.commit()
        return OwnedItemResponse.model_validate(owned_item)

    async def patch_owned(
        self, user: User, owned_item_id: UUID, payload: CollectionPatchRequest
    ) -> OwnedItemResponse:
        owned_item = await self.collection.get_owned(user.id, owned_item_id)
        if owned_item is None or owned_item.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection item not found")

        fields = payload.model_fields_set
        next_edition_id = payload.edition_id if "edition_id" in fields else owned_item.edition_id
        next_variant_id = payload.variant_id if "variant_id" in fields else owned_item.variant_id

        try:
            await self.metadata.validate_refs(owned_item.item_id, next_edition_id, next_variant_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        for field in ("edition_id", "variant_id", "condition", "grade", "personal_notes", "client_updated_at"):
            if field in fields:
                setattr(owned_item, field, getattr(payload, field))

        await self._record_owned_change(user.id, owned_item, SyncAction.upsert)
        await self.db.commit()
        return OwnedItemResponse.model_validate(owned_item)

    async def delete_owned(self, user: User, owned_item_id: UUID) -> None:
        owned_item = await self.collection.get_owned(user.id, owned_item_id)
        if owned_item is None or owned_item.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection item not found")
        owned_item.mark_deleted()
        await self._record_owned_change(user.id, owned_item, SyncAction.delete)
        await self.db.commit()

    async def _record_owned_change(
        self, user_id: UUID, owned_item: OwnedItem, action: SyncAction, device_id: str | None = None
    ) -> SyncChange:
        return await self.sync.record(
            SyncChange(
                user_id=user_id,
                entity_type="owned_item",
                entity_id=owned_item.id,
                device_id=device_id,
                action=action,
                payload=OwnedItemResponse.model_validate(owned_item).model_dump(mode="json"),
            )
        )
