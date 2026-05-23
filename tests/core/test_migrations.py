from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.session import AsyncSessionLocal


def test_alembic_has_single_head(migrated_database):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert len(script.get_heads()) == 1


@pytest.mark.asyncio
async def test_generalized_catalog_schema_exists(migrated_database):
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
        assert {
            "organizations",
            "persons",
            "entity_organizations",
            "entity_persons",
            "story_arcs",
            "story_arc_items",
            "characters",
            "character_appearances",
            "tags",
            "entity_tags",
            "image_assets",
            "image_cache_entries",
            "tracking_entries",
            "admin_audit_logs",
        }.issubset(tables)

        enum_values = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select enumlabel
                        from pg_enum
                        join pg_type on pg_type.oid = pg_enum.enumtypid
                        where pg_type.typname = 'item_kind'
                        """
                    )
                )
            ).all()
        }
        assert {
            "comic",
            "manga",
            "anime",
            "movie",
            "tv",
            "game",
            "boardgame",
            "book",
            "music",
        }.issubset(enum_values)

        provider_values = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select enumlabel
                        from pg_enum
                        join pg_type on pg_type.oid = pg_enum.enumtypid
                        where pg_type.typname = 'external_provider'
                        """
                    )
                )
            ).all()
        }
        assert "gcd" in provider_values
