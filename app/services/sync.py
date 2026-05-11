from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import SyncAction
from app.models.sync import SyncChange
from app.models.user import OwnedItem, User
from app.repositories.collection import CollectionRepository
from app.repositories.metadata import MetadataRepository
from app.repositories.sync import SyncRepository
from app.schemas.collection import CollectionAddRequest, OwnedItemResponse
from app.schemas.sync import ClientChange, SyncPullResponse, SyncPushRequest, SyncPushResponse


class SyncService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.collection = CollectionRepository(db)
        self.metadata = MetadataRepository(db)
        self.sync = SyncRepository(db)

    async def pull(self, user: User, since: datetime | None) -> SyncPullResponse:
        collection = await self.collection.list_owned(user.id, include_deleted=True)
        changes = await self.sync.changes_since(user.id, since)
        return SyncPullResponse(
            server_time=datetime.now(UTC),
            collection=[OwnedItemResponse.model_validate(item) for item in collection],
            changes=changes,
        )

    async def changes_since(self, user: User, since: datetime | None):
        return await self.sync.changes_since(user.id, since)

    async def push(self, user: User, payload: SyncPushRequest) -> SyncPushResponse:
        accepted_changes = []
        for change in payload.changes:
            accepted_changes.append(await self._apply_owned_item_change(user, change, payload.device_id))
        await self.db.commit()
        return SyncPushResponse(accepted=len(accepted_changes), changes=accepted_changes)

    async def _apply_owned_item_change(
        self, user: User, change: ClientChange, request_device_id: str | None
    ) -> SyncChange:
        if change.entity_type != "owned_item":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported entity type")

        owned_item = None
        if change.entity_id is not None:
            owned_item = await self.collection.get_owned(user.id, change.entity_id)

        if change.action == SyncAction.delete:
            if owned_item is None:
                return await self._record_tombstone(user.id, change, request_device_id)
            owned_item.mark_deleted()
            return await self._record_change(
                user.id, owned_item, SyncAction.delete, change.device_id or request_device_id
            )

        if owned_item is not None and self._server_wins(owned_item, change):
            return await self._record_change(
                user.id, owned_item, SyncAction.upsert, change.device_id or request_device_id
            )

        request = CollectionAddRequest(**change.payload)
        try:
            await self.metadata.validate_refs(request.item_id, request.edition_id, request.variant_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        if owned_item is None:
            owned_item = OwnedItem(
                id=change.entity_id or self._payload_id(change) or uuid4(),
                user_id=user.id,
                collection_id=request.collection_id or await self.collection.default_collection_id(user.id),
                item_id=request.item_id,
            )
            self.db.add(owned_item)

        owned_item.edition_id = request.edition_id
        owned_item.variant_id = request.variant_id
        owned_item.condition = request.condition
        owned_item.grade = request.grade
        owned_item.personal_notes = request.personal_notes
        owned_item.client_updated_at = change.client_changed_at or request.client_updated_at
        owned_item.deleted_at = None
        await self.db.flush()
        return await self._record_change(
            user.id, owned_item, SyncAction.upsert, change.device_id or request_device_id
        )

    def _server_wins(self, owned_item: OwnedItem, change: ClientChange) -> bool:
        if change.client_changed_at is None or owned_item.client_updated_at is None:
            return False
        return owned_item.client_updated_at > change.client_changed_at

    async def _record_tombstone(
        self, user_id: UUID, change: ClientChange, request_device_id: str | None
    ) -> SyncChange:
        return await self.sync.record(
            SyncChange(
                user_id=user_id,
                entity_type=change.entity_type,
                entity_id=change.entity_id or self._payload_id(change) or uuid4(),
                device_id=change.device_id or request_device_id,
                action=SyncAction.delete,
                payload=change.payload,
            )
        )

    def _payload_id(self, change: ClientChange) -> UUID | None:
        raw_id = change.payload.get("id")
        if raw_id is None:
            return None
        return UUID(str(raw_id))

    async def _record_change(
        self, user_id: UUID, owned_item: OwnedItem, action: SyncAction, device_id: str | None
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
