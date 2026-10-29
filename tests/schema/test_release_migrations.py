from uuid import uuid4

import pytest
from sqlalchemy import MetaData, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schema_migrations import (
    BASELINE_TABLE_NAMES,
    GAMES_TABLE_NAMES,
    MIGRATION_METADATA,
    RELEASE_TABLE_NAMES,
    migrate_schema,
    release_tables,
    schema_migrations,
)
from app.db.session import engine
from app.models import CanonicalCorrectionProposal, CanonicalCorrectionProposalValue, EntityAlias
from app.models.base import ItemKind
from app.models.catalog_game_item import GameItem
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
            assert (await connection.execute(select(schema_migrations.c.version).order_by(schema_migrations.c.version))).scalars().all() == [1, 2, 3]
            album_id = uuid4()
            await connection.execute(MusicItem.__table__.insert().values(id=album_id, title="Preserved edition"))
            await migrate_schema(connection)
            assert (await connection.execute(select(MusicItem.title).where(MusicItem.id == album_id))).scalar_one() == "Preserved edition"
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                summary = await AdminMetadataService(session).catalog_summary()
                assert summary.items_by_kind == {"music": 1, "comic": 0, "game": 0, "game_hardware": 0, "game_toy": 0}
            columns = await connection.run_sync(lambda conn: inspect(conn).get_columns("music_items", schema=schema))
            assert {column["name"] for column in columns} == set(MusicItem.__table__.columns.keys())
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


@pytest.mark.db
@pytest.mark.usefixtures("clean_database")
@pytest.mark.asyncio
@pytest.mark.parametrize("baseline_version", [1, 2])
async def test_released_baseline_upgrade_preserves_music_and_games(baseline_version):
    schema = "release_games_" + uuid4().hex
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            metadata = MetaData()
            baseline_tables = BASELINE_TABLE_NAMES | (
                GAMES_TABLE_NAMES if baseline_version == 2 else frozenset()
            )
            for table in release_tables(baseline_tables):
                table.to_metadata(metadata, schema=schema)
            await connection.run_sync(metadata.create_all)
            # The released person tables that migration 3 drops.
            await connection.execute(text("CREATE TABLE persons (id uuid PRIMARY KEY, name varchar(255) NOT NULL)"))
            await connection.execute(text(
                "CREATE TABLE entity_persons (id uuid PRIMARY KEY, entity_type varchar(64) NOT NULL, "
                "entity_id uuid NOT NULL, person_id uuid NOT NULL REFERENCES persons(id) ON DELETE CASCADE, "
                "role varchar(64) NOT NULL)"
            ))
            await connection.run_sync(MIGRATION_METADATA.create_all)
            await connection.execute(schema_migrations.insert(), [
                {"version": version} for version in range(1, baseline_version + 1)
            ])
            album_id = uuid4()
            await connection.execute(MusicItem.__table__.insert().values(
                id=album_id, title="Keep this album"))
            person_id = uuid4()
            await connection.execute(text("INSERT INTO persons VALUES (:id, 'Retired person')"), {"id": person_id})
            await connection.execute(text(
                "INSERT INTO entity_persons VALUES (:id, 'catalog_music_item', :album, :person, 'artist')"
            ), {"id": uuid4(), "album": album_id, "person": person_id})
            await connection.execute(EntityAlias.__table__.insert(), [
                {"id": uuid4(), "entity_type": "person", "entity_id": person_id, "alias": "Gone", "normalized_alias": "gone", "position": 0},
                {"id": uuid4(), "entity_type": "catalog_music_item", "entity_id": album_id, "alias": "Kept", "normalized_alias": "kept", "position": 0},
            ])
            game_id = uuid4()
            if baseline_version == 2:
                await connection.execute(GameItem.__table__.insert().values(
                    id=game_id, title="Keep this game",
                    details={"creators": [{"name": "Studio", "role": "Developer", "person_id": "p1"}]},
                ))
                game_correction_id = uuid4()
                await connection.execute(CanonicalCorrectionProposal.__table__.insert().values(
                    id=game_correction_id, kind=ItemKind.game, entity_type="catalog_game_item",
                    entity_id=game_id, scope="catalog", base_hash="before", status="pending"))
                await connection.execute(CanonicalCorrectionProposalValue.__table__.insert(), [
                    {"id": uuid4(), "proposal_id": game_correction_id, "path": path, "value_type": "string"}
                    for path in ("/title", "/creators/0/person_id")
                ])
            await migrate_schema(connection)
            assert (await connection.execute(select(MusicItem.title).where(
                MusicItem.id == album_id))).scalar_one() == "Keep this album"
            if baseline_version == 2:
                assert (await connection.execute(select(GameItem.title).where(
                    GameItem.id == game_id))).scalar_one() == "Keep this game"
                assert (await connection.execute(select(GameItem.details).where(
                    GameItem.id == game_id))).scalar_one() == {"creators": [{"name": "Studio", "role": "Developer"}]}
                assert (await connection.execute(select(CanonicalCorrectionProposalValue.path).where(
                    CanonicalCorrectionProposalValue.proposal_id == game_correction_id))).scalars().all() == ["/title"]
            assert (await connection.execute(select(EntityAlias.alias))).scalars().all() == ["Kept"]
            names = set(await connection.run_sync(
                lambda conn: inspect(conn).get_table_names(schema=schema)))
            assert names == RELEASE_TABLE_NAMES | {"schema_migrations"}
            versions = (await connection.execute(select(schema_migrations.c.version).order_by(
                schema_migrations.c.version))).scalars().all()
            assert versions == [1, 2, 3]
            await migrate_schema(connection)
            assert (await connection.execute(select(schema_migrations.c.version).order_by(
                schema_migrations.c.version))).scalars().all() == [1, 2, 3]
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
