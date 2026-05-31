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


def test_media_catalog_keeps_hidden_video_formats_off_top_level_routes():
    top_level_kinds = {media_type.kind for media_type in top_level_media_types}
    bluray = media_type_for_route("blu-ray")
    movies = media_type_for_kind(ItemKind.movie)
    tv = media_type_for_kind(ItemKind.tv)
    # `anime` kind removed; video kinds are covered by `movie` and `tv`

    assert ItemKind.bluray not in top_level_kinds
    assert ItemKind.tv not in top_level_kinds
    assert bluray is not None
    assert bluray.kind == ItemKind.bluray
    assert bluray.is_top_level is False
    assert bluray.default_provider is None
    assert [format.id for format in bluray.physical_formats] == ["blu-ray"]
    assert movies is not None
    assert tv is not None
    assert tv.is_top_level is False
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
    assert is_video_item_kind(ItemKind.movie) is True
    assert is_video_item_kind(ItemKind.comic) is False


def test_media_catalog_maps_route_segments_and_default_providers():
    comics = media_type_for_route("comics")
    # `manga` and `anime` kinds removed
    assert not hasattr(ItemKind, "manga")
    assert not hasattr(ItemKind, "anime")
    manga = None
    anime = None
    games = media_type_for_kind(ItemKind.game)

    assert comics is not None
    assert comics.kind == ItemKind.comic
    assert comics.default_provider == ExternalProvider.gcd
    assert comics.providers == (ExternalProvider.gcd, ExternalProvider.comicvine, ExternalProvider.mangadex, ExternalProvider.anilist)
    # `manga` and `anime` kinds removed — mappings are folded into `comic`/`movie`
    assert manga is None
    assert anime is None
    assert games is not None
    assert games.default_provider == ExternalProvider.igdb


def test_provider_registry_can_filter_and_pick_media_defaults():
    registry = ProviderRegistry()

    comic_providers = registry.for_kind(ItemKind.comic)

    assert [provider.name for provider in comic_providers] == ["comicvine", "gcd", "anilist", "mangadex"]
    assert registry.default_for_kind(ItemKind.comic).name == "gcd"
    assert registry.default_for_kind(ItemKind.game).name == "igdb"
    assert registry.default_for_kind(ItemKind.movie).name == "tmdb"
    assert registry.default_for_kind(ItemKind.tv).name == "tmdb"
    assert registry.default_for_kind(ItemKind.bluray) is None
    assert registry.default_for_kind(ItemKind.book).name == "openlibrary"
    # Removed kinds: no defaults for `manga`/`anime`
    assert registry.default_for_kind(ItemKind.boardgame).name == "bgg"
    assert registry.default_for_kind(ItemKind.music).name == "musicbrainz"
