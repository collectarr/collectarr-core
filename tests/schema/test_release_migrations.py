from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schema_migrations import RELEASE_TABLE_NAMES, migrate_schema, schema_migrations
from app.db.session import engine
from app.models.catalog_music_item import MusicItem
from app.services.admin import AdminMetadataService


@pytest.mark.db
@pytest.mark.usefixtures("clean_database")
@pytest.mark.asyncio
async def test_current_music_shape_installs_once_at_baseline_one():
    schema = "release_baseline_" + uuid4().hex
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            await migrate_schema(connection)
            names = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names(schema=schema)))
            assert names == RELEASE_TABLE_NAMES | {"schema_migrations"}
            assert (await connection.execute(select(schema_migrations.c.version))).scalars().all() == [1]
            album_id = uuid4()
            await connection.execute(MusicItem.__table__.insert().values(id=album_id, title="Preserved edition"))
            await migrate_schema(connection)
            assert (await connection.execute(select(MusicItem.title).where(MusicItem.id == album_id))).scalar_one() == "Preserved edition"
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                summary = await AdminMetadataService(session).catalog_summary()
                assert summary.items_by_kind == {"music": 1}
            columns = await connection.run_sync(lambda conn: inspect(conn).get_columns("music_items", schema=schema))
            assert {column["name"] for column in columns} == set(MusicItem.__table__.columns.keys())
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
