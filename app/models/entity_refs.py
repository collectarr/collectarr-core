from __future__ import annotations

from dataclasses import dataclass

from app.models.base import ItemKind


@dataclass(frozen=True)
class EntityRefSpec:
    entity_type: str
    table_name: str
    display_name: str
    kind: ItemKind | None = None
    supports_aliases: bool = False
    supports_links: bool = False
    supports_provider_ids: bool = False


@dataclass(frozen=True)
class EntityRefRegistry:
    specs_by_entity_type: dict[str, EntityRefSpec]

    def table_name(self, entity_type: str) -> str | None:
        spec = self.spec_for(entity_type)
        return spec.table_name if spec is not None else None

    def is_known(self, entity_type: str) -> bool:
        return entity_type in self.specs_by_entity_type

    def spec_for(self, entity_type: str) -> EntityRefSpec | None:
        return self.specs_by_entity_type.get(entity_type)

    def known_entity_types(self) -> tuple[str, ...]:
        return tuple(sorted(self.specs_by_entity_type))


DEFAULT_ENTITY_REF_REGISTRY = EntityRefRegistry(
    {
        "bundle_release": EntityRefSpec(
            "bundle_release",
            "bundle_releases",
            "Bundle release",
            supports_aliases=True,
            supports_links=True,
            supports_provider_ids=True,
        ),
        "anime_series": EntityRefSpec("anime_series", "anime_series", "Anime series", kind=ItemKind.anime, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "boardgame_work": EntityRefSpec("boardgame_work", "boardgame_works", "Board game work", kind=ItemKind.boardgame, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "boardgame_edition": EntityRefSpec("boardgame_edition", "boardgame_editions", "Board game edition", kind=ItemKind.boardgame, supports_links=True, supports_provider_ids=True),
        "book_work": EntityRefSpec("book_work", "book_works", "Book work", kind=ItemKind.book, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "book_edition": EntityRefSpec("book_edition", "book_editions", "Book edition", kind=ItemKind.book, supports_links=True, supports_provider_ids=True),
        "comic_work": EntityRefSpec("comic_work", "comic_works", "Comic work", kind=ItemKind.comic, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "comic_volume": EntityRefSpec("comic_volume", "comic_volumes", "Comic volume", kind=ItemKind.comic, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "comic_issue": EntityRefSpec("comic_issue", "comic_issues", "Comic issue", kind=ItemKind.comic, supports_links=True, supports_provider_ids=True),
        "comic_series": EntityRefSpec("comic_series", "comic_series", "Comic series", kind=ItemKind.comic, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "game_work": EntityRefSpec("game_work", "game_works", "Game work", kind=ItemKind.game, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "game_release": EntityRefSpec("game_release", "game_releases", "Game release", kind=ItemKind.game, supports_links=True, supports_provider_ids=True),
        "manga_series": EntityRefSpec("manga_series", "manga_series", "Manga series", kind=ItemKind.manga, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "manga_work": EntityRefSpec("manga_work", "manga_works", "Manga work", kind=ItemKind.manga, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "movie_work": EntityRefSpec("movie_work", "movie_works", "Movie work", kind=ItemKind.movie, supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "music_release": EntityRefSpec("music_release", "music_releases", "Music release", kind=ItemKind.music, supports_links=True, supports_provider_ids=True),
        "tv_release": EntityRefSpec("tv_release", "tv_releases", "TV release", kind=ItemKind.tv, supports_links=True, supports_provider_ids=True),
        "character": EntityRefSpec("character", "characters", "Character", supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "story_arc": EntityRefSpec("story_arc", "story_arcs", "Story arc", supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "organization": EntityRefSpec("organization", "organizations", "Organization", supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "person": EntityRefSpec("person", "persons", "Person", supports_aliases=True, supports_links=True, supports_provider_ids=True),
        "tag": EntityRefSpec("tag", "tags", "Tag", supports_aliases=True, supports_links=True, supports_provider_ids=True),
    }
)
