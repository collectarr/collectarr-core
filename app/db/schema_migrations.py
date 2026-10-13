"""Ordered release migrations; never bootstrap an unversioned existing database."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, MetaData, Table, func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import Base

CURRENT_SCHEMA_VERSION = 1

# Shared catalog support and administration plus the sole released kind.
RELEASE_TABLE_NAMES = frozenset({
    "users", "music_items", "organizations", "persons",
    "entity_organizations", "entity_persons", "entity_aliases", "entity_links",
    "tags", "entity_tags", "image_assets", "metadata_taxonomies",
    "physical_format_refs", "release_statuses", "catalog_item_proposals",
    "admin_audit_logs", "admin_audit_log_details", "duplicate_reviews",
    "duplicate_review_entities", "duplicate_review_details",
    "canonical_correction_proposals", "canonical_correction_proposal_values",
})

MIGRATION_METADATA = MetaData()
schema_migrations = Table(
    "schema_migrations", MIGRATION_METADATA,
    Column("version", Integer, primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


def release_tables() -> list[Table]:
    tables = [table for table in Base.metadata.sorted_tables if table.name in RELEASE_TABLE_NAMES]
    missing = RELEASE_TABLE_NAMES - {table.name for table in tables}
    if missing:
        raise RuntimeError(f"Release table definitions are missing: {sorted(missing)}")
    for table in tables:
        for foreign_key in table.foreign_keys:
            if foreign_key.column.table.name not in RELEASE_TABLE_NAMES:
                raise RuntimeError(f"Release schema references an unreleased table: {foreign_key}")
    return tables


async def migrate_schema(connection: AsyncConnection) -> None:
    """Install the current shape at baseline 1, or verify a versioned database.

    Future versions add explicit steps here. This function never drops data,
    guesses an unversioned schema, or imports a historical v1 implementation.
    The caller owns the transaction.
    """
    await connection.execute(text("SELECT pg_advisory_xact_lock(83412701)"))
    schema = (await connection.execute(text("SELECT current_schema()"))).scalar_one()
    existing = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names(schema=schema)))
    if "schema_migrations" not in existing:
        if existing:
            raise RuntimeError("Existing unversioned database left untouched; use a new release database.")
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        metadata = MetaData()
        for table in release_tables():
            table.to_metadata(metadata, schema=schema)
        await connection.run_sync(metadata.create_all)
        await connection.run_sync(MIGRATION_METADATA.create_all)
        await connection.execute(schema_migrations.insert().values(version=1))
        return
    versions = list((await connection.execute(select(schema_migrations.c.version).order_by(schema_migrations.c.version))).scalars())
    if versions != [1]:
        raise RuntimeError(f"Unsupported schema migration history: {versions}")
    expected = RELEASE_TABLE_NAMES | {"schema_migrations"}
    if existing != expected:
        raise RuntimeError("Versioned database tables differ from the released schema; database left untouched.")
