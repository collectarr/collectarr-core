import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, func, select, text

from app.db.schema_migrations import (
    BOOKS_TABLE_NAMES,
    MIGRATION_METADATA,
    RELEASE_TABLE_NAMES,
    migrate_schema,
    release_tables,
    schema_migrations,
)
from app.db.session import engine
from app.models.catalog_game_item import GameItem


@pytest.mark.db
@pytest.mark.usefixtures("clean_database")
@pytest.mark.asyncio
async def test_game_identity_upgrade_preserves_released_editions_and_does_not_merge_titles():
    schema = "release_game_ids_" + uuid4().hex
    original_ids = [uuid4(), uuid4(), uuid4()]
    timestamp = datetime(2025, 1, 2, tzinfo=UTC)
    details = {"platforms": ["PS5"], "cover_image_url": "edition.webp"}
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            metadata = MetaData()
            for table in release_tables(RELEASE_TABLE_NAMES - BOOKS_TABLE_NAMES):
                if table.name != "game_items":
                    table.to_metadata(metadata, schema=schema)
            await connection.run_sync(metadata.create_all)
            # Frozen released schema 3: do not create this table from the new model.
            await connection.execute(text('''CREATE TABLE game_items (
                id uuid PRIMARY KEY, title varchar(255) NOT NULL,
                sort_key varchar(255), barcode varchar(100), catalog_number varchar(100),
                details jsonb NOT NULL, revision integer NOT NULL DEFAULT 1,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )'''))
            await connection.run_sync(MIGRATION_METADATA.create_all)
            await connection.execute(schema_migrations.insert(), [{"version": version} for version in [1, 2, 3]])
            for index, item_id in enumerate(original_ids):
                await connection.execute(text('''INSERT INTO game_items
                    (id, title, barcode, details, revision, created_at, updated_at)
                    VALUES (:id, 'Same title', :barcode, CAST(:details AS jsonb), 7, :at, :at)'''),
                    {"id": item_id, "barcode": str(index) if index < 2 else None,
                     "details": json.dumps(details), "at": timestamp})
            await migrate_schema(connection)
            rows = (await connection.execute(select(GameItem.__table__).where(GameItem.id.in_(original_ids)))).mappings().all()
            by_id = {row["id"]: row for row in rows}
            assert set(by_id) == set(original_ids)
            for row in rows:
                assert row["revision"] == 7
                assert row["details"] == details
                assert row["created_at"] == timestamp
                assert row["updated_at"] == timestamp
            first_parent = by_id[original_ids[0]]["parent_game_id"]
            second_parent = by_id[original_ids[1]]["parent_game_id"]
            assert first_parent is not None and second_parent is not None
            assert first_parent != second_parent
            assert by_id[original_ids[2]]["parent_game_id"] is None
            assert await connection.scalar(select(func.count()).select_from(GameItem)) == 5
            assert (await connection.execute(select(schema_migrations.c.version).order_by(schema_migrations.c.version))).scalars().all() == [1, 2, 3, 4]
            await migrate_schema(connection)
            assert await connection.scalar(select(func.count()).select_from(GameItem)) == 5
    finally:
        assert schema.startswith("release_game_ids_")
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
