from __future__ import annotations

import asyncio
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from app.db.session import engine

BASELINE_REVISION = "20260624_1000"
HEAD_REVISION = "20260626_1100"


def _alembic_config() -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    return Config(str(repo_root / "alembic.ini"))


async def _table_names() -> list[str]:
    async with engine.connect() as connection:
        return await connection.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())


async def _inspect_database_state() -> tuple[bool, bool]:
    """Return (has_user_tables, has_alembic_version)."""
    try:
        tables = await _table_names()
        has_alembic_version = "alembic_version" in tables
        user_tables = [name for name in tables if name != "alembic_version"]
        return bool(user_tables), has_alembic_version
    finally:
        await engine.dispose()


def main() -> None:
    has_user_tables, has_alembic_version = asyncio.run(_inspect_database_state())
    config = _alembic_config()

    if not has_user_tables:
        # Fresh database: build the schema through the migration itself so the
        # baseline revision is the single source of truth (no create_all).
        command.upgrade(config, "head")
        return

    if not has_alembic_version:
        # Pre-existing schema without Alembic bookkeeping: adopt the baseline.
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()