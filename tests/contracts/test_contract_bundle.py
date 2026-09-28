import json

from scripts.export_contract_bundle import CONTRACT_VERSION, write_contract_bundle


def test_contract_bundle_exports_catalog_item_contract_and_kinds(tmp_path):
    hashes = write_contract_bundle(tmp_path)

    manifest = json.loads((tmp_path / "contract-manifest.json").read_text(encoding="utf-8"))
    catalog_item = json.loads((tmp_path / "catalog-item-v1.json").read_text(encoding="utf-8"))
    active_kinds = json.loads((tmp_path / "active-kinds.json").read_text(encoding="utf-8"))

    assert manifest["contractVersion"] == CONTRACT_VERSION
    assert manifest["openApiHash"] == hashes["openapi.json"]
    assert manifest["catalogItemHash"] == hashes["catalog-item-v1.json"]
    assert manifest["activeKindsHash"] == hashes["active-kinds.json"]
    assert "fieldSchemaHash" not in manifest
    assert manifest["generatedAt"]
    assert manifest["coreCommit"]

    assert catalog_item["schemaVersion"] == 1
    assert "CatalogItemWriteV1" in catalog_item["$defs"]
    assert active_kinds["contractVersion"] == CONTRACT_VERSION
    assert active_kinds["kinds"] == [
        "anime", "boardgame", "book", "comic", "game", "manga", "movie", "music", "tv"
    ]
