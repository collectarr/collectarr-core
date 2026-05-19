from app.catalog.media_types import (
    media_type_for_kind,
    media_type_for_route,
    media_types,
    top_level_media_types,
)
from app.catalog.physical_formats import (
    is_video_item_kind,
    physical_format_for_id,
    video_physical_formats,
)
from app.models.base import ExternalProvider, ItemKind
from app.providers.registry import ProviderRegistry


def test_media_catalog_covers_all_item_kinds():
    configured_kinds = {media_type.kind for media_type in media_types}

    assert configured_kinds == set(ItemKind)


def test_media_catalog_keeps_bluray_as_legacy_physical_format():
    top_level_kinds = {media_type.kind for media_type in top_level_media_types}
    bluray = media_type_for_route("blu-ray")
    movies = media_type_for_kind(ItemKind.movie)
    tv = media_type_for_kind(ItemKind.tv)

    assert ItemKind.bluray not in top_level_kinds
    assert bluray is not None
    assert bluray.kind == ItemKind.bluray
    assert bluray.is_top_level is False
    assert bluray.legacy_of == ItemKind.movie
    assert bluray.default_provider is None
    assert [format.id for format in bluray.physical_formats] == ["blu-ray"]
    assert movies is not None
    assert tv is not None
    assert [format.id for format in movies.physical_formats] == [
        "dvd",
        "blu-ray",
        "4k-uhd",
        "vhs",
        "laserdisc",
        "digital",
    ]
    assert movies.physical_formats == video_physical_formats
    assert tv.physical_formats == video_physical_formats
    assert physical_format_for_id(" Blu-Ray ") is not None
    assert physical_format_for_id("4K Blu-ray") is not None
    assert is_video_item_kind(ItemKind.movie) is True
    assert is_video_item_kind(ItemKind.tv) is True
    assert is_video_item_kind(ItemKind.comic) is False


def test_media_catalog_maps_route_segments_and_default_providers():
    comics = media_type_for_route("comics")
    manga = media_type_for_kind(ItemKind.manga)
    anime = media_type_for_kind(ItemKind.anime)
    games = media_type_for_kind(ItemKind.game)

    assert comics is not None
    assert comics.kind == ItemKind.comic
    assert comics.default_provider == ExternalProvider.gcd
    assert comics.providers == (ExternalProvider.gcd, ExternalProvider.comicvine)
    assert manga is not None
    assert manga.default_provider == ExternalProvider.mangadex
    assert manga.providers == (
        ExternalProvider.mangadex,
        ExternalProvider.anilist,
        ExternalProvider.comicvine,
    )
    assert anime is not None
    assert anime.default_provider == ExternalProvider.anilist
    assert anime.providers == (ExternalProvider.anilist, ExternalProvider.tmdb)
    assert games is not None
    assert games.default_provider == ExternalProvider.igdb


def test_provider_registry_can_filter_and_pick_media_defaults():
    registry = ProviderRegistry()

    comic_providers = registry.for_kind(ItemKind.comic)

    assert [provider.name for provider in comic_providers] == ["comicvine", "gcd"]
    assert [provider.name for provider in registry.for_kind(ItemKind.manga)] == [
        "comicvine",
        "anilist",
        "mangadex",
    ]
    assert [provider.name for provider in registry.for_kind(ItemKind.anime)] == [
        "tmdb",
        "anilist",
    ]
    assert registry.default_for_kind(ItemKind.comic).name == "gcd"
    assert registry.default_for_kind(ItemKind.game).name == "igdb"
    assert registry.default_for_kind(ItemKind.movie).name == "tmdb"
    assert registry.default_for_kind(ItemKind.tv).name == "tmdb"
    assert registry.default_for_kind(ItemKind.anime).name == "anilist"
    assert registry.default_for_kind(ItemKind.bluray) is None
    assert registry.default_for_kind(ItemKind.book).name == "openlibrary"
    assert registry.default_for_kind(ItemKind.manga).name == "mangadex"
    assert registry.default_for_kind(ItemKind.boardgame).name == "bgg"
    assert registry.default_for_kind(ItemKind.music).name == "musicbrainz"
