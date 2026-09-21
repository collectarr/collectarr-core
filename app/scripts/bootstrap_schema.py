"""Create the server schema directly from the typed SQLAlchemy models."""

from __future__ import annotations

import asyncio

from app.db.session import engine
from app.models import Base


async def main() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
