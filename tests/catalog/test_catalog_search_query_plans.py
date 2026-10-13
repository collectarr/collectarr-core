from __future__ import annotations

import re

import pytest
from sqlalchemy import bindparam, select, text
from sqlalchemy.dialects import postgresql

from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS
from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.services.catalog_item_search import CatalogItemSearchService


async def _explain(db, statement) -> str:
    compiled = statement.compile(dialect=postgresql.dialect(paramstyle="named"))
    sql = re.sub(
        r":([A-Za-z0-9_]+)::([A-Za-z0-9_]+)",
        r"CAST(:\1 AS \2)",
        str(compiled),
    )
    query = text(f"EXPLAIN (FORMAT TEXT) {sql}").bindparams(
        *[bindparam(name, type_=compiled.binds[name].type) for name in compiled.params]
    )
    rows = await db.execute(query, compiled.params)
    return "\n".join(row[0] for row in rows)


@pytest.mark.asyncio
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

            if (
                definition.kind is ItemKind.music
                or "identifiers" not in definition.document.children
            ):
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
