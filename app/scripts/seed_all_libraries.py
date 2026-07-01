"""Seed a compact native dataset for all library kinds."""

from __future__ import annotations

import asyncio

from app.db.session import AsyncSessionLocal
from app.scripts.seed_native_catalog import seed_catalog


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        await seed_catalog(db, entries_per_kind=1)


if __name__ == "__main__":
    asyncio.run(seed())
