from app.catalog.media_types import media_type_for_kind, media_type_for_route, media_types
from app.models.base import ExternalProvider, ItemKind
from app.providers.registry import ProviderRegistry


def test_media_catalog_covers_all_item_kinds():
    configured_kinds = {media_type.kind for media_type in media_types}

    assert configured_kinds == set(ItemKind)


def test_media_catalog_maps_route_segments_and_default_providers():
    comics = media_type_for_route("comics")
    bluray = media_type_for_route("blu-ray")
    games = media_type_for_kind(ItemKind.game)

    assert comics is not None
    assert comics.kind == ItemKind.comic
    assert comics.default_provider == ExternalProvider.gcd
    assert comics.providers == (ExternalProvider.gcd, ExternalProvider.comicvine)
    assert bluray is not None
    assert bluray.kind == ItemKind.bluray
    assert games is not None
    assert games.default_provider == ExternalProvider.igdb


def test_provider_registry_can_filter_and_pick_media_defaults():
    registry = ProviderRegistry()

    comic_providers = registry.for_kind(ItemKind.comic)

    assert [provider.name for provider in comic_providers] == ["comicvine", "gcd"]
    assert registry.default_for_kind(ItemKind.comic).name == "gcd"
    assert registry.default_for_kind(ItemKind.game).name == "igdb"
    assert registry.default_for_kind(ItemKind.bluray).name == "tmdb"
    assert registry.default_for_kind(ItemKind.book).name == "openlibrary"
    assert registry.default_for_kind(ItemKind.manga).name == "anilist"
    assert registry.default_for_kind(ItemKind.boardgame).name == "bgg"
    assert registry.default_for_kind(ItemKind.music).name == "musicbrainz"
