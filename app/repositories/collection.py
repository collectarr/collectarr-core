from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import OwnedItem, UserCollection


class CollectionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def default_collection_id(self, user_id: UUID) -> UUID:
        result = await self.db.execute(
            select(UserCollection).where(UserCollection.user_id == user_id).order_by(UserCollection.created_at)
        )
        collection = result.scalars().first()
        if collection is None:
            collection = UserCollection(user_id=user_id, name="Default")
            self.db.add(collection)
            await self.db.flush()
        return collection.id

    async def list_owned(self, user_id: UUID, include_deleted: bool = False) -> list[OwnedItem]:
        stmt = select(OwnedItem).where(OwnedItem.user_id == user_id).order_by(OwnedItem.updated_at.desc())
        if not include_deleted:
            stmt = stmt.where(OwnedItem.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        return list(result.scalars())

    async def get_owned(self, user_id: UUID, owned_item_id: UUID) -> OwnedItem | None:
        result = await self.db.execute(
            select(OwnedItem).where(OwnedItem.user_id == user_id, OwnedItem.id == owned_item_id)
        )
        return result.scalar_one_or_none()

    async def changed_since(self, user_id: UUID, since: datetime) -> list[OwnedItem]:
        result = await self.db.execute(
            select(OwnedItem)
            .where(OwnedItem.user_id == user_id, OwnedItem.updated_at > since)
            .order_by(OwnedItem.updated_at)
        )
        return list(result.scalars())

    async def add(self, owned_item: OwnedItem) -> OwnedItem:
        self.db.add(owned_item)
        await self.db.flush()
        return owned_item

