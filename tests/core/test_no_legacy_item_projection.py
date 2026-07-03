from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_legacy_item_projection_tables_and_fks_do_not_exist(migrated_database):
    async with AsyncSessionLocal() as db:
        tables = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select table_name
                        from information_schema.tables
                        where table_schema = 'public'
                        """
                    )
                )
            ).all()
        }

        assert "items" not in tables
        assert "editions" not in tables
        assert "variants" not in tables

        fk_rows = (
            await db.execute(
                text(
                    """
                    select con.conname
                    from pg_constraint con
                    join pg_class rel on rel.oid = con.conrelid
                    join pg_class frel on frel.oid = con.confrelid
                    join pg_namespace fnsp on fnsp.oid = frel.relnamespace
                    where con.contype = 'f'
                      and fnsp.nspname = 'public'
                      and frel.relname = 'items'
                    """
                )
            )
        ).all()

        assert fk_rows == []


def test_services_do_not_import_legacy_projection_models():
    services_dir = Path(__file__).resolve().parents[2] / "app" / "services"
    legacy_names = {"Item", "Edition", "Variant"}
    violations: list[str] = []

    for path in services_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            if not module.startswith("app.models"):
                continue
            for alias in node.names:
                if alias.name in legacy_names:
                    violations.append(f"{path}:{alias.name}")

    assert violations == []
