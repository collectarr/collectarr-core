from __future__ import annotations

import json
from pathlib import Path

from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS


def test_metadata_field_schema_uses_only_registered_catalog_kinds():
    contracts_dir = Path(__file__).resolve().parents[2] / "contracts"
    field_schema = json.loads(
        (contracts_dir / "metadata-field-schema.json").read_text(encoding="utf-8")
    )
    kinds = {definition.kind.value for definition in CATALOG_KIND_DEFINITIONS}
    assert {row["kind"] for row in field_schema["fields"]} <= kinds
    assert all(
        not {"sourceTable", "sourceEntityType", "scope", "writeTarget"}.intersection(row)
        for row in field_schema["fields"]
    )
