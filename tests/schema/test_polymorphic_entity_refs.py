import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.models.entity_refs import DEFAULT_ENTITY_REF_REGISTRY


def _entity_table(entity_type: str) -> str:
    table_name = DEFAULT_ENTITY_REF_REGISTRY.table_name(entity_type)
    assert table_name is not None, f"unexpected entity_type {entity_type!r}"
    return table_name


async def _assert_rows_reference_existing_entities(
    db,
    *,
    source_table: str,
    where_clause: str = "",
) -> None:
    stmt = f"select entity_type, entity_id from {source_table} {where_clause}"
    rows = (await db.execute(text(stmt))).all()
    for entity_type, entity_id in rows:
        table_name = _entity_table(entity_type)
        exists = await db.execute(
            text(f"select 1 from {table_name} where id = :entity_id limit 1"),
            {"entity_id": entity_id},
        )
        assert exists.first() is not None, f"missing {entity_type} row for {source_table}.entity_id={entity_id}"


@pytest.mark.asyncio
async def test_entity_aliases_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_aliases")


@pytest.mark.asyncio
async def test_entity_links_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_links")


@pytest.mark.asyncio
async def test_bundle_release_components_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="bundle_release_components")


@pytest.mark.asyncio
async def test_entity_organizations_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_organizations")


@pytest.mark.asyncio
async def test_entity_persons_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_persons")


@pytest.mark.asyncio
async def test_entity_tags_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        await _assert_rows_reference_existing_entities(db, source_table="entity_tags")
