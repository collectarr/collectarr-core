from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync import SyncChange


class SyncRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(self, change: SyncChange) -> SyncChange:
        self.db.add(change)
        await self.db.flush()
        return change

    async def changes_since(self, user_id: UUID, since: datetime | None) -> list[SyncChange]:
        stmt = select(SyncChange).where(SyncChange.user_id == user_id).order_by(SyncChange.changed_at)
        if since is not None:
            stmt = stmt.where(SyncChange.changed_at > since)
        result = await self.db.execute(stmt)
        return list(result.scalars())

