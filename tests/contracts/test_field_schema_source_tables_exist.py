from __future__ import annotations

import json
from pathlib import Path

from app.models.base import Base


def test_metadata_field_schema_source_tables_exist():
    contracts_dir = Path(__file__).resolve().parents[2] / "contracts"
    field_schema = json.loads(
        (contracts_dir / "metadata-field-schema.json").read_text(encoding="utf-8")
    )
    source_tables = {
        row["sourceTable"]
        for row in field_schema["fields"]
        if row.get("sourceTable")
    }

    assert source_tables <= set(Base.metadata.tables)
