from dataclasses import dataclass

from app.models.base import ExternalProvider, ItemKind


@dataclass(frozen=True)
class MediaTypeConfig:
    kind: ItemKind
    singular_label: str
    plural_label: str
    route_segments: tuple[str, ...]
    default_provider: ExternalProvider | None = None
    providers: tuple[ExternalProvider, ...] = ()

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
        providers=(ExternalProvider.gcd, ExternalProvider.comicvine),
    ),
    MediaTypeConfig(
        kind=ItemKind.manga,
        singular_label="Manga",
        plural_label="Manga",
        route_segments=("manga",),
        default_provider=ExternalProvider.anilist,
        providers=(ExternalProvider.anilist,),
    ),
    MediaTypeConfig(
        kind=ItemKind.anime,
        singular_label="Anime",
        plural_label="Anime",
        route_segments=("anime",),
        default_provider=ExternalProvider.anilist,
        providers=(ExternalProvider.anilist,),
    ),
    MediaTypeConfig(
        kind=ItemKind.movie,
        singular_label="Movie",
        plural_label="Movies",
        route_segments=("movies", "movie"),
        default_provider=ExternalProvider.tmdb,
        providers=(ExternalProvider.tmdb,),
    ),
    MediaTypeConfig(
        kind=ItemKind.tv,
        singular_label="TV Show",
        plural_label="TV Shows",
        route_segments=("tv", "shows", "series"),
        default_provider=ExternalProvider.tmdb,
        providers=(ExternalProvider.tmdb,),
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
        providers=(ExternalProvider.openlibrary,),
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
        singular_label="Blu-ray",
        plural_label="Blu-rays",
        route_segments=("blu-ray", "blu-rays", "bluray"),
        default_provider=ExternalProvider.tmdb,
        providers=(ExternalProvider.tmdb,),
    ),
)

_MEDIA_TYPES_BY_KIND = {config.kind: config for config in media_types}
_MEDIA_TYPES_BY_ROUTE = {
    route_segment: config for config in media_types for route_segment in config.route_segments
}


def media_type_for_kind(kind: ItemKind) -> MediaTypeConfig | None:
    return _MEDIA_TYPES_BY_KIND.get(kind)


def media_type_for_route(route_segment: str) -> MediaTypeConfig | None:
    return _MEDIA_TYPES_BY_ROUTE.get(route_segment.strip().lower())
