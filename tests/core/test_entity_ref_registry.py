from app.models.base import ItemKind
from app.models.entity_refs import DEFAULT_ENTITY_REF_REGISTRY


def test_entity_ref_registry_exposes_bundle_release_spec():
    spec = DEFAULT_ENTITY_REF_REGISTRY.spec_for("bundle_release")

    assert spec is not None
    assert spec.table_name == "bundle_releases"
    assert spec.display_name == "Bundle release"
    assert spec.supports_provider_ids
    assert DEFAULT_ENTITY_REF_REGISTRY.table_name("bundle_release") == "bundle_releases"


def test_entity_ref_registry_marks_active_entities_with_kind_metadata():
    book_spec = DEFAULT_ENTITY_REF_REGISTRY.spec_for("book_work")
    game_spec = DEFAULT_ENTITY_REF_REGISTRY.spec_for("game_release")

    assert book_spec is not None and book_spec.kind == ItemKind.book
    assert game_spec is not None and game_spec.kind == ItemKind.game
    assert DEFAULT_ENTITY_REF_REGISTRY.is_known("book_work")
    assert "bundle_release" in DEFAULT_ENTITY_REF_REGISTRY.known_entity_types()
