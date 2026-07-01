"""Seed a richer native dataset for all library kinds."""

from __future__ import annotations

import asyncio
import sys

from app.db.session import AsyncSessionLocal, engine
from app.models import Base
from app.scripts.seed_native_catalog import seed_catalog, wipe_seed_data


async def seed() -> None:
    wipe = "--wipe" in sys.argv

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        if wipe:
            await wipe_seed_data(db)
        await seed_catalog(db, entries_per_kind=2)


if __name__ == "__main__":
    asyncio.run(seed())
