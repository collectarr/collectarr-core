"""Ordered release migrations; never bootstrap an unversioned existing database."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Column, DateTime, Integer, MetaData, Table, func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import Base

CURRENT_SCHEMA_VERSION = 3

# Shared catalog support and administration plus the sole released kind.
BASELINE_TABLE_NAMES = frozenset({
    "users", "music_items", "organizations",
    "entity_organizations", "entity_aliases", "entity_links",
    "tags", "entity_tags", "image_assets", "metadata_taxonomies",
    "physical_format_refs", "release_statuses", "catalog_item_proposals",
    "admin_audit_logs", "admin_audit_log_details", "duplicate_reviews",
    "duplicate_review_entities", "duplicate_review_details",
    "canonical_correction_proposals", "canonical_correction_proposal_values",
})
# Released in baseline 1 and dropped by migration 3: credits are names on
# each item, so no kind references shared person records.
RETIRED_PERSON_TABLE_NAMES = frozenset({"persons", "entity_persons"})
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
    installed = "schema_migrations" not in existing
    if installed:
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
    if versions[-1] < 3 and not installed:
        # A new install skips the person tables that migration 3 drops.
        expected |= RETIRED_PERSON_TABLE_NAMES
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
        quoted_schema = '"' + schema.replace('"', '""') + '"'
        if not installed:
            # Person records were only ever reachable through admin tools, so
            # drop them with everything that points at them.
            for table in (
                "entity_organizations", "entity_aliases", "entity_links", "entity_tags",
                "image_assets", "duplicate_reviews", "canonical_correction_proposals",
            ):
                await connection.execute(text(
                    f"DELETE FROM {quoted_schema}.{table} WHERE entity_type = 'person'"
                ))
            await connection.execute(text(f"DROP TABLE {quoted_schema}.entity_persons"))
            await connection.execute(text(f"DROP TABLE {quoted_schema}.persons"))
            # Game credits are names too: strip the released person ids.
            await _strip_json(connection, quoted_schema, "game_items", "details", _without_game_person_ids)
            await _strip_json(
                connection, quoted_schema, "catalog_item_proposals", "catalog_item",
                _without_game_person_ids, where="kind = 'game'",
            )
            await _delete_correction_values(
                connection, quoted_schema, "game", "^/(creators|contributors)/[0-9]+/person_id(/|$)"
            )
        # Add Comics from the released schema 2 without replacing existing data.
        metadata = MetaData()
        for table in release_tables(COMICS_TABLE_NAMES):
            table.to_metadata(metadata, schema=schema)
        await connection.run_sync(metadata.create_all)
        await connection.execute(schema_migrations.insert().values(version=3))


def _without_key(rows: Any, key: str) -> Any:
    """Drop one key from each object in a stored list of credits."""
    if not isinstance(rows, list):
        return rows
    return [{k: v for k, v in row.items() if k != key} if isinstance(row, dict) else row for row in rows]


def _without_game_person_ids(document: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _without_key(value, "person_id") if key in ("creators", "contributors") else value
        for key, value in document.items()
    }


async def _strip_json(
    connection: AsyncConnection, quoted_schema: str, table: str, column: str, strip, *, where: str = "true",
) -> None:
    rows = await connection.execute(text(f"SELECT id, {column} FROM {quoted_schema}.{table} WHERE {where}"))
    for row in rows.mappings():
        stripped = strip(row[column])
        if stripped != row[column]:
            await connection.execute(text(
                f"UPDATE {quoted_schema}.{table} SET {column} = CAST(:value AS jsonb) WHERE id = :id"
            ), {"id": row["id"], "value": json.dumps(stripped)})


async def _delete_correction_values(connection: AsyncConnection, quoted_schema: str, kind: str, path: str) -> None:
    await connection.execute(text(
        f"DELETE FROM {quoted_schema}.canonical_correction_proposal_values AS v "
        f"USING {quoted_schema}.canonical_correction_proposals AS p "
        "WHERE v.proposal_id = p.id AND CAST(p.kind AS text) = :kind AND v.path ~ :path"
    ), {"kind": kind, "path": path})
