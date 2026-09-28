from __future__ import annotations

import json
from pathlib import Path

from scripts.export_contract_bundle import build_contract_bundle


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_contracts_match_generated_bundle() -> None:
    contracts_dir = Path(__file__).resolve().parents[2] / "contracts"
    bundle = build_contract_bundle()

    assert _load_json(contracts_dir / "openapi.json") == bundle["openapi"]
    committed_catalog_item = _load_json(contracts_dir / "catalog-item-v1.json")
    committed_active_kinds = _load_json(contracts_dir / "active-kinds.json")

    assert committed_catalog_item["schemaVersion"] == bundle["catalog_item"]["schemaVersion"]
    assert committed_catalog_item["$defs"] == bundle["catalog_item"]["$defs"]
    assert committed_active_kinds["contractVersion"] == bundle["active_kinds"]["contractVersion"]
    assert committed_active_kinds["kinds"] == bundle["active_kinds"]["kinds"]
    assert not (contracts_dir / "metadata-field-schema.json").exists()
