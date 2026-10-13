from app.main import app


def test_metadata_routes_use_typed_paths():
    paths = set(app.openapi()["paths"])
    assert "/api/v1/metadata/field-schema" in paths
    assert "/api/v1/metadata/correction-targets/{kind}/{entity_id}" in paths
    assert not any(path.startswith("/api/v1/metadata/items") for path in paths)
