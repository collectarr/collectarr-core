from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db.session import engine
from app.models import Base


BASELINE_REVISION = "20260529_0001"
HEAD_REVISION = "202605180001"


def _alembic_config() -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    return Config(str(repo_root / "alembic.ini"))


async def _table_names() -> list[str]:
    async with engine.connect() as connection:
        return await connection.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())


async def _create_schema_from_metadata() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def main() -> None:
    tables = await _table_names()
    has_alembic_version = "alembic_version" in tables
    user_tables = [name for name in tables if name != "alembic_version"]

    if not user_tables:
        await _create_schema_from_metadata()
        await engine.dispose()
        command.stamp(_alembic_config(), HEAD_REVISION)
        return

    await engine.dispose()
    config = _alembic_config()
    if not has_alembic_version:
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")


if __name__ == "__main__":
    asyncio.run(main())