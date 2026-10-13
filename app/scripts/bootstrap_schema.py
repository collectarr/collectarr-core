"""Apply explicit release migrations to a new or versioned database."""

from __future__ import annotations

import asyncio

from app.db.schema_migrations import migrate_schema
from app.db.session import engine


async def main() -> None:
    async with engine.begin() as connection:
        await migrate_schema(connection)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
