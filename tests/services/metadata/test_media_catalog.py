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


def test_media_catalog_covers_all_item_kinds():
    configured_kinds = {media_type.kind for media_type in media_types}

    assert configured_kinds == set(ItemKind)


def test_media_catalog_keeps_video_formats_within_active_top_level_routes():
    top_level_kinds = {media_type.kind for media_type in top_level_media_types}
    anime = media_type_for_kind(ItemKind.anime)
    movies = media_type_for_kind(ItemKind.movie)
    tv = media_type_for_kind(ItemKind.tv)

    assert ItemKind.tv in top_level_kinds
    assert ItemKind.anime in top_level_kinds
    assert media_type_for_route("blu-ray") is None
    assert media_type_for_route("bluray") is None
    assert movies is not None
    assert tv is not None
    assert tv.is_top_level is True
    assert [format.id for format in movies.physical_formats] == [
        "dvd",
        "blu-ray",
        "4k-uhd",
        "vhs",
        "laserdisc",
        "digital",
    ]
    assert movies.physical_formats == video_physical_formats
    assert anime is not None
    assert anime.physical_formats == video_physical_formats
    assert tv.physical_formats == video_physical_formats
    assert physical_format_for_id(" Blu-Ray ") is not None
    assert physical_format_for_id("4K Blu-ray") is not None
    assert is_video_item_kind(ItemKind.anime) is True
    assert is_video_item_kind(ItemKind.movie) is True
    assert is_video_item_kind(ItemKind.tv) is True
    assert is_video_item_kind(ItemKind.comic) is False


def test_media_catalog_maps_route_segments_and_default_providers():
    comics = media_type_for_route("comics")
    manga = media_type_for_route("manga")
    anime = media_type_for_route("anime")
    games = media_type_for_kind(ItemKind.game)

    assert comics is not None
    assert comics.kind == ItemKind.comic
    assert comics.default_provider == ExternalProvider.gcd
    assert comics.providers == (ExternalProvider.gcd, ExternalProvider.comicvine)
    assert manga is not None
    assert manga.default_provider == ExternalProvider.hardcover
    assert anime is not None
    assert anime.default_provider == ExternalProvider.anilist
    assert games is not None
    assert games.default_provider == ExternalProvider.igdb
