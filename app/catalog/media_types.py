from dataclasses import dataclass

from app.catalog.physical_formats import PhysicalFormatConfig, video_physical_formats
from app.models.base import ExternalProvider, ItemKind


MEDIA_CATALOG_CONTRACT_VERSION = 1
CATALOG_SNAPSHOT_SCHEMA_VERSION = 1
DEFAULT_PROVIDER_SEARCH_POLICY = "core_miss_then_configured_providers"


@dataclass(frozen=True)
class MediaTypeConfig:
    kind: ItemKind
    singular_label: str
    plural_label: str
    route_segments: tuple[str, ...]
    default_provider: ExternalProvider | None = None
    providers: tuple[ExternalProvider, ...] = ()
    item_number_sort_padding: int | None = None
    is_top_level: bool = True
    legacy_of: ItemKind | None = None
    physical_formats: tuple[PhysicalFormatConfig, ...] = ()
    provider_search_policy: str = DEFAULT_PROVIDER_SEARCH_POLICY

    @property
    def primary_route_segment(self) -> str:
        return self.route_segments[0] if self.route_segments else ""


media_types: tuple[MediaTypeConfig, ...] = (
    MediaTypeConfig(
        kind=ItemKind.comic,
        singular_label="Comic",
        plural_label="Comics",
        route_segments=("comics", "comic"),
        default_provider=ExternalProvider.gcd,
        providers=(
            ExternalProvider.gcd,
            ExternalProvider.comicvine,
            ExternalProvider.mangadex,
            ExternalProvider.anilist,
        ),
        item_number_sort_padding=6,
    ),
    # 'manga' and 'anime' removed — their provider support moved into comics/movies
    MediaTypeConfig(
        kind=ItemKind.movie,
        singular_label="Movie",
        plural_label="Movies",
        route_segments=("movies", "movie"),
        default_provider=ExternalProvider.tmdb,
        providers=(ExternalProvider.tmdb, ExternalProvider.anilist),
        physical_formats=video_physical_formats,
    ),
    MediaTypeConfig(
        kind=ItemKind.tv,
        singular_label="TV Show",
        plural_label="TV Shows",
        route_segments=("tv", "shows", "series"),
        default_provider=ExternalProvider.tmdb,
        providers=(ExternalProvider.tmdb,),
        physical_formats=video_physical_formats,
    ),
    MediaTypeConfig(
        kind=ItemKind.game,
        singular_label="Game",
        plural_label="Games",
        route_segments=("games", "game"),
        default_provider=ExternalProvider.igdb,
        providers=(ExternalProvider.igdb,),
    ),
    MediaTypeConfig(
        kind=ItemKind.boardgame,
        singular_label="Board Game",
        plural_label="Board Games",
        route_segments=("board-games", "boardgames", "boardgame"),
        default_provider=ExternalProvider.bgg,
        providers=(ExternalProvider.bgg,),
    ),
    MediaTypeConfig(
        kind=ItemKind.book,
        singular_label="Book",
        plural_label="Books",
        route_segments=("books", "book"),
        default_provider=ExternalProvider.openlibrary,
        providers=(ExternalProvider.openlibrary, ExternalProvider.hardcover),
    ),
    MediaTypeConfig(
        kind=ItemKind.music,
        singular_label="Music Release",
        plural_label="Music Releases",
        route_segments=("music",),
        default_provider=ExternalProvider.musicbrainz,
        providers=(ExternalProvider.musicbrainz,),
    ),
    MediaTypeConfig(
        kind=ItemKind.bluray,
        singular_label="Legacy Blu-ray",
        plural_label="Legacy Blu-rays",
        route_segments=("blu-ray", "blu-rays", "bluray"),
        is_top_level=False,
        legacy_of=ItemKind.movie,
        physical_formats=tuple(
            physical_format
            for physical_format in video_physical_formats
            if physical_format.id == "blu-ray"
        ),
    ),
)

top_level_media_types: tuple[MediaTypeConfig, ...] = tuple(
    config for config in media_types if config.is_top_level
)

_MEDIA_TYPES_BY_KIND = {config.kind: config for config in media_types}
_MEDIA_TYPES_BY_ROUTE = {
    route_segment: config for config in media_types for route_segment in config.route_segments
}


def media_type_for_kind(kind: ItemKind) -> MediaTypeConfig | None:
    return _MEDIA_TYPES_BY_KIND.get(kind)


def media_type_for_route(route_segment: str) -> MediaTypeConfig | None:
    return _MEDIA_TYPES_BY_ROUTE.get(route_segment.strip().lower())
