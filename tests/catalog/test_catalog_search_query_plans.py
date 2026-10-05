from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql

from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS
from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.services.catalog_item_search import CatalogItemSearchService


def _literal_sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


async def _explain(db, statement) -> str:
    rows = await db.execute(text(f"EXPLAIN (FORMAT TEXT) {_literal_sql(statement)}"))
    return "\n".join(row[0] for row in rows)


async def test_identifier_and_scalar_lookups_can_use_declared_indexes(
    schema_database,
) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL enable_seqscan = off"))

        for definition in CATALOG_KIND_DEFINITIONS:
            model = definition.model
            barcode_plan = await _explain(
                db,
                select(model.id).where(model.barcode == "0000000000000"),
            )
            assert f"ix_{model.__tablename__}_barcode" in barcode_plan

            catalog_number_plan = await _explain(
                db,
                select(model.id).where(model.catalog_number == "CAT-0001"),
            )
            assert f"ix_{model.__tablename__}_catalog_number" in catalog_number_plan

            if definition.kind is ItemKind.music:
                continue
            identifier_match = CatalogItemSearchService._identifier_match(
                definition,
                "9780000000000",
            )
            identifier_plan = await _explain(
                db,
                select(model.id).where(identifier_match),
            )
            assert f"ix_{model.__tablename__}_details_gin" in identifier_plan
