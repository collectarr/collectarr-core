"""Ordered release migrations; never bootstrap an unversioned existing database."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, MetaData, Table, func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import Base

CURRENT_SCHEMA_VERSION = 3

# Shared catalog support and administration plus the sole released kind.
BASELINE_TABLE_NAMES = frozenset({
    "users", "music_items", "organizations", "persons",
    "entity_organizations", "entity_persons", "entity_aliases", "entity_links",
    "tags", "entity_tags", "image_assets", "metadata_taxonomies",
    "physical_format_refs", "release_statuses", "catalog_item_proposals",
    "admin_audit_logs", "admin_audit_log_details", "duplicate_reviews",
    "duplicate_review_entities", "duplicate_review_details",
    "canonical_correction_proposals", "canonical_correction_proposal_values",
})
GAMES_TABLE_NAMES = frozenset({"game_items", "game_hardware_items", "game_toy_items"})
COMICS_TABLE_NAMES = frozenset({"comic_items"})
RELEASE_TABLE_NAMES = BASELINE_TABLE_NAMES | GAMES_TABLE_NAMES | COMICS_TABLE_NAMES

MIGRATION_METADATA = MetaData()
schema_migrations = Table(
    "schema_migrations", MIGRATION_METADATA,
    Column("version", Integer, primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


def release_tables(names: frozenset[str] = RELEASE_TABLE_NAMES) -> list[Table]:
    tables = [table for table in Base.metadata.sorted_tables if table.name in names]
    missing = names - {table.name for table in tables}
    if missing:
        raise RuntimeError(f"Release table definitions are missing: {sorted(missing)}")
    for table in tables:
        for foreign_key in table.foreign_keys:
            if foreign_key.column.table.name not in RELEASE_TABLE_NAMES:
                raise RuntimeError(f"Release schema references an unreleased table: {foreign_key}")
    return tables


async def migrate_schema(connection: AsyncConnection) -> None:
    """Install baseline 1, then run ordered upgrades in the caller's transaction."""
    await connection.execute(text("SELECT pg_advisory_xact_lock(83412701)"))
    schema = (await connection.execute(text("SELECT current_schema()"))).scalar_one()
    existing = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names(schema=schema)))
    if "schema_migrations" not in existing:
        if existing:
            raise RuntimeError("Existing unversioned database left untouched; use a new release database.")
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        metadata = MetaData()
        for table in release_tables(BASELINE_TABLE_NAMES):
            table.to_metadata(metadata, schema=schema)
        await connection.run_sync(metadata.create_all)
        await connection.run_sync(MIGRATION_METADATA.create_all)
        await connection.execute(schema_migrations.insert().values(version=1))
        existing = BASELINE_TABLE_NAMES | {"schema_migrations"}
    versions = list((await connection.execute(select(schema_migrations.c.version).order_by(schema_migrations.c.version))).scalars())
    if (not versions or versions[-1] > CURRENT_SCHEMA_VERSION
            or versions != list(range(1, versions[-1] + 1))):
        raise RuntimeError(f"Unsupported schema migration history: {versions}")
    expected = BASELINE_TABLE_NAMES | {"schema_migrations"}
    if versions[-1] >= 2:
        expected |= GAMES_TABLE_NAMES
    if versions[-1] >= 3:
        expected |= COMICS_TABLE_NAMES
    if existing != expected:
        raise RuntimeError("Versioned database tables differ from the released schema; database left untouched.")
    if versions[-1] < 2:
        # Independent catalog inventories. No Game row is reinterpreted as a
        # Hardware/Toy row and no existing table or record is replaced.
        type_schema = (await connection.execute(text(
            "SELECT n.nspname FROM pg_type t "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE t.typname = 'item_kind' "
            "ORDER BY CASE WHEN n.nspname = :schema THEN 0 ELSE 1 END LIMIT 1"
        ), {"schema": schema})).scalar_one_or_none()
        if type_schema is not None:
            quoted_target = '"' + type_schema.replace('"', '""') + '"'
            for value in ("game_hardware", "game_toy"):
                await connection.execute(text(
                    f"ALTER TYPE {quoted_target}.item_kind ADD VALUE IF NOT EXISTS '{value}'"
                ))
        metadata = MetaData()
        for table in release_tables(GAMES_TABLE_NAMES):
            table.to_metadata(metadata, schema=schema)
        await connection.run_sync(metadata.create_all)
        await connection.execute(schema_migrations.insert().values(version=2))

    if versions[-1] < 3:
        # Add Comics from the released schema 2 without replacing existing data.
        metadata = MetaData()
        for table in release_tables(COMICS_TABLE_NAMES):
            table.to_metadata(metadata, schema=schema)
        await connection.run_sync(metadata.create_all)
        await connection.execute(schema_migrations.insert().values(version=3))
