from app.catalog.media_types import (
    media_type_for_kind,
    media_type_for_route,
    media_types,
    top_level_media_types,
)
from app.models.base import ItemKind


def test_media_catalog_exposes_music_and_internal_collections():
    assert {item.kind for item in media_types} == {
        ItemKind.music, ItemKind.game, ItemKind.game_hardware, ItemKind.game_toy, ItemKind.collection,
    }
    assert {item.kind for item in top_level_media_types} == {ItemKind.music, ItemKind.game}


def test_unreleased_kind_routes_are_not_resolved():
    for kind in ItemKind:
        if kind not in {ItemKind.music, ItemKind.game, ItemKind.game_hardware, ItemKind.game_toy, ItemKind.collection}:
            assert media_type_for_kind(kind) is None
    for route in ("comics", "books", "manga", "anime", "movies", "tv", "blu-ray"):
        assert media_type_for_route(route) is None


def test_music_route_preserves_its_catalog_labels():
    music = media_type_for_route("music")
    assert music is not None and music.kind is ItemKind.music
    assert music.plural_label == "Music Releases"
