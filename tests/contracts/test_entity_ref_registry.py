from app.models.base import ItemKind
from app.models.entity_refs import DEFAULT_ENTITY_REF_REGISTRY


def test_unreleased_entities_are_not_resolvable():
    for entity in ("bundle_release", "catalog_book_item", "catalog_tv_item", "character", "story_arc"):
        assert DEFAULT_ENTITY_REF_REGISTRY.spec_for(entity) is None


def test_registry_exposes_music_and_its_shared_references():
    spec = DEFAULT_ENTITY_REF_REGISTRY.spec_for("catalog_music_item")
    assert spec is not None and spec.kind is ItemKind.music
    assert spec.table_name == "music_items"
    assert set(DEFAULT_ENTITY_REF_REGISTRY.known_entity_types()) == {
        "catalog_music_item", "catalog_game_item", "catalog_game_hardware_item",
        "catalog_game_toy_item", "organization", "person", "tag",
    }
