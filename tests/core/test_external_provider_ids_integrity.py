import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.models.entity_refs import DEFAULT_ENTITY_REF_REGISTRY


@pytest.mark.asyncio
async def test_external_provider_ids_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    """
                    select entity_type, entity_id
                    from external_provider_ids
                    order by entity_type, entity_id
                    """
                )
            )
        ).all()

        assert rows, "expected at least one external provider id"
        for entity_type, entity_id in rows:
            table_name = DEFAULT_ENTITY_REF_REGISTRY.table_name(entity_type)
            assert table_name is not None, f"unexpected entity_type {entity_type!r}"
            exists = await db.execute(
                text(f"select 1 from {table_name} where id = :entity_id limit 1"),
                {"entity_id": entity_id},
            )
            assert exists.first() is not None, (
                f"missing {entity_type} row for external_provider_ids.entity_id={entity_id}"
            )
