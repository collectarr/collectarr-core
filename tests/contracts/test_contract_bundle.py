import json

from scripts.export_contract_bundle import CONTRACT_VERSION, write_contract_bundle


def test_contract_bundle_exports_versioned_snapshot(tmp_path):
    hashes = write_contract_bundle(tmp_path)

    manifest = json.loads((tmp_path / "contract-manifest.json").read_text(encoding="utf-8"))
    field_schema = json.loads((tmp_path / "metadata-field-schema.json").read_text(encoding="utf-8"))
    active_kinds = json.loads((tmp_path / "active-kinds.json").read_text(encoding="utf-8"))

    assert manifest["contractVersion"] == CONTRACT_VERSION
    assert manifest["openApiHash"] == hashes["openapi.json"]
    assert manifest["fieldSchemaHash"] == hashes["metadata-field-schema.json"]
    assert manifest["activeKindsHash"] == hashes["active-kinds.json"]
    assert manifest["generatedAt"]
    assert manifest["coreCommit"]

    assert field_schema["contractVersion"] == CONTRACT_VERSION
    assert field_schema["fields"]
    book_release_date = next(
        row
        for row in field_schema["fields"]
        if row["key"] == "release_date" and row["kind"] == "book"
    )
    assert book_release_date["editable"] is True
    assert book_release_date["valueType"] == "partial_date"
    assert not {"scope", "writeTarget", "sourceEntityType", "sourceTable"}.intersection(
        book_release_date
    )

    assert "collection" not in active_kinds["kinds"]
    assert len(active_kinds["kinds"]) == 9
