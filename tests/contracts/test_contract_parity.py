from __future__ import annotations

import json
from pathlib import Path

from app.models.base import ItemKind
from app.providers.registry import ProviderRegistry
from scripts.export_contract_bundle import build_contract_bundle


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_contracts_match_generated_bundle() -> None:
    contracts_dir = Path(__file__).resolve().parents[2] / "contracts"
    bundle = build_contract_bundle()

    assert _load_json(contracts_dir / "openapi.json") == bundle["openapi"]
    committed_field_schema = _load_json(contracts_dir / "metadata-field-schema.json")
    committed_active_kinds = _load_json(contracts_dir / "active-kinds.json")
    committed_provider_support = _load_json(contracts_dir / "provider-support.json")

    assert committed_field_schema["contractVersion"] == bundle["field_schema"]["contractVersion"]
    assert committed_field_schema["fields"] == bundle["field_schema"]["fields"]
    assert committed_active_kinds["contractVersion"] == bundle["active_kinds"]["contractVersion"]
    assert committed_active_kinds["kinds"] == bundle["active_kinds"]["kinds"]
    assert committed_provider_support["contractVersion"] == bundle["provider_support"]["contractVersion"]


def test_provider_support_matrix_only_exposes_known_kinds() -> None:
    registry = ProviderRegistry()
    supported_kinds = {kind.value for kind in ItemKind}

    for row in registry.status_entries():
        assert row.kind.value in supported_kinds
        assert set(kind.value for kind in row.supported_kinds) <= supported_kinds


def test_provider_support_matrix_matches_committed_stable_fields() -> None:
    contracts_dir = Path(__file__).resolve().parents[2] / "contracts"
    committed = _load_json(contracts_dir / "provider-support.json")["providers"]
    generated = build_contract_bundle()["provider_support"]["providers"]

    stable_keys = (
        "name",
        "displayName",
        "kind",
        "supportedKinds",
        "supportsSearch",
        "supportsIngest",
        "requiresUserKey",
        "nonCommercialOnly",
        "allowsRedistribution",
        "allowsImageMirroring",
        "requiresAttribution",
        "licenseName",
        "termsUrl",
        "attributionUrl",
        "rateLimit",
        "cachePolicy",
    )

    assert [
        {key: row.get(key) for key in stable_keys}
        for row in committed
    ] == [
        {key: row.get(key) for key in stable_keys}
        for row in generated
    ]
