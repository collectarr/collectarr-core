from uuid import uuid4

import pytest
from sqlalchemy import MetaData, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schema_migrations import (
    BASELINE_TABLE_NAMES,
    MIGRATION_METADATA,
    RELEASE_TABLE_NAMES,
    migrate_schema,
    release_tables,
    schema_migrations,
)
from app.db.session import engine
from app.models.catalog_music_item import MusicItem
from app.services.admin import AdminMetadataService


@pytest.mark.db
@pytest.mark.usefixtures("clean_database")
@pytest.mark.asyncio
async def test_current_shape_installs_ordered_migrations_once():
    schema = "release_baseline_" + uuid4().hex
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            await migrate_schema(connection)
            names = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names(schema=schema)))
            assert names == RELEASE_TABLE_NAMES | {"schema_migrations"}
            assert (await connection.execute(select(schema_migrations.c.version).order_by(schema_migrations.c.version))).scalars().all() == [1, 2]
            album_id = uuid4()
            await connection.execute(MusicItem.__table__.insert().values(id=album_id, title="Preserved edition"))
            await migrate_schema(connection)
            assert (await connection.execute(select(MusicItem.title).where(MusicItem.id == album_id))).scalar_one() == "Preserved edition"
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                summary = await AdminMetadataService(session).catalog_summary()
                assert summary.items_by_kind == {"music": 1, "game": 0, "game_hardware": 0, "game_toy": 0}
            columns = await connection.run_sync(lambda conn: inspect(conn).get_columns("music_items", schema=schema))
            assert {column["name"] for column in columns} == set(MusicItem.__table__.columns.keys())
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


@pytest.mark.db
@pytest.mark.usefixtures("clean_database")
@pytest.mark.asyncio
async def test_baseline_one_upgrade_preserves_music_and_adds_three_independent_tables():
    schema = "release_games_" + uuid4().hex
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            metadata = MetaData()
            for table in release_tables(BASELINE_TABLE_NAMES):
                table.to_metadata(metadata, schema=schema)
            await connection.run_sync(metadata.create_all)
            await connection.run_sync(MIGRATION_METADATA.create_all)
            await connection.execute(schema_migrations.insert().values(version=1))
            album_id = uuid4()
            await connection.execute(MusicItem.__table__.insert().values(
                id=album_id, title="Keep this album"))
            await migrate_schema(connection)
            assert (await connection.execute(select(MusicItem.title).where(
                MusicItem.id == album_id))).scalar_one() == "Keep this album"
            names = set(await connection.run_sync(
                lambda conn: inspect(conn).get_table_names(schema=schema)))
            assert names == RELEASE_TABLE_NAMES | {"schema_migrations"}
            versions = (await connection.execute(select(schema_migrations.c.version).order_by(
                schema_migrations.c.version))).scalars().all()
            assert versions == [1, 2]
            await migrate_schema(connection)
            assert (await connection.execute(select(schema_migrations.c.version).order_by(
                schema_migrations.c.version))).scalars().all() == [1, 2]
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


@pytest.mark.db
@pytest.mark.usefixtures("clean_database")
@pytest.mark.asyncio
@pytest.mark.parametrize("version", [None, 2])
async def test_unsupported_existing_schema_keeps_its_tables_and_data(version):
    schema = "release_baseline_" + uuid4().hex
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            await connection.execute(text("CREATE TABLE preserved (value text)"))
            await connection.execute(text("INSERT INTO preserved VALUES ('data')"))
            if version is not None:
                await connection.run_sync(schema_migrations.create)
                await connection.execute(schema_migrations.insert().values(version=version))
            with pytest.raises(RuntimeError):
                await migrate_schema(connection)
            assert (await connection.execute(text("SELECT value FROM preserved"))).scalar_one() == "data"
            names = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names(schema=schema)))
            assert names == ({"preserved"} if version is None else {"preserved", "schema_migrations"})
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
