"""Administrative retention operations for typed provider provenance."""

from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProviderPayloadSnapshot, ProviderPayloadSnapshotValue


class AdminSnapshotService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def purge_expired(self, *, limit: int = 5000) -> int:
        now = datetime.now(UTC)
        snapshot_ids = list(
            (
                await self.db.execute(
                    select(ProviderPayloadSnapshot.id)
                    .where(
                        ProviderPayloadSnapshot.purged_at.is_(None),
                        ProviderPayloadSnapshot.expires_at.is_not(None),
                        ProviderPayloadSnapshot.expires_at <= now,
                    )
                    .order_by(ProviderPayloadSnapshot.expires_at.asc())
                    .limit(limit)
                )
            ).scalars()
        )
        if not snapshot_ids:
            return 0
        await self.db.execute(
            delete(ProviderPayloadSnapshotValue).where(
                ProviderPayloadSnapshotValue.snapshot_id.in_(snapshot_ids)
            )
        )
        await self.db.execute(
            update(ProviderPayloadSnapshot)
            .where(ProviderPayloadSnapshot.id.in_(snapshot_ids))
            .values(purged_at=now)
        )
        await self.db.flush()
        return len(snapshot_ids)
