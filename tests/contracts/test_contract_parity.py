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
    committed_field_schema = _load_json(contracts_dir / "metadata-field-schema.json")
    committed_catalog_item_schema = _load_json(contracts_dir / "catalog-item-v2.json")
    committed_active_kinds = _load_json(contracts_dir / "active-kinds.json")

    assert committed_field_schema["contractVersion"] == bundle["field_schema"]["contractVersion"]
    assert committed_field_schema["fields"] == bundle["field_schema"]["fields"]
    assert committed_catalog_item_schema["kinds"] == bundle["catalog_item_schema"]["kinds"]
    assert committed_catalog_item_schema["schemaVersion"] == 2
    assert committed_catalog_item_schema["contractVersion"] == "2.0.0"
    assert committed_active_kinds["contractVersion"] == bundle["active_kinds"]["contractVersion"]
    assert committed_active_kinds["kinds"] == bundle["active_kinds"]["kinds"]
    assert "provider_support" not in bundle
    assert "provider_envelope_schema" not in bundle
    assert "golden_provider_envelopes" not in bundle
