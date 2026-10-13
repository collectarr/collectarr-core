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
        ),
        "catalog_anime_item": EntityRefSpec("catalog_anime_item", "anime_items", "Anime Catalog Item", kind=ItemKind.anime, supports_aliases=True, supports_links=True),
        "catalog_boardgame_item": EntityRefSpec(
            "catalog_boardgame_item",
            "boardgame_items",
            "Board game catalog item",
            kind=ItemKind.boardgame,
            supports_aliases=True,
            supports_links=True,
        ),
        "catalog_book_item": EntityRefSpec(
            "catalog_book_item",
            "book_items",
            "Book catalog item",
            kind=ItemKind.book,
            supports_links=True,
        ),
        "book_series": EntityRefSpec(
            "book_series",
            "book_series",
            "Book series",
            kind=ItemKind.book,
            supports_aliases=True,
            supports_links=True,
        ),
        "catalog_comic_item": EntityRefSpec(
            "catalog_comic_item",
            "comic_items",
            "Comic Catalog Item",
            kind=ItemKind.comic,
            supports_aliases=True,
            supports_links=True,
        ),
        "catalog_game_item": EntityRefSpec(
            "catalog_game_item",
            "game_items",
            "Game catalog item",
            kind=ItemKind.game,
            supports_aliases=True,
            supports_links=True,
        ),
        "catalog_manga_item": EntityRefSpec(
            "catalog_manga_item",
            "manga_items",
            "Manga Catalog Item",
            kind=ItemKind.manga,
            supports_aliases=True,
            supports_links=True,
        ),
        "catalog_movie_item": EntityRefSpec(
            "catalog_movie_item",
            "movie_items",
            "Movie catalog item",
            kind=ItemKind.movie,
            supports_aliases=True,
            supports_links=True,
        ),
        "catalog_music_item": EntityRefSpec(
            "catalog_music_item",
            "music_items",
            "Music catalog item",
            kind=ItemKind.music,
            supports_aliases=True,
            supports_links=True,
        ),
        "catalog_tv_item": EntityRefSpec("catalog_tv_item", "tv_items", "TV Catalog Item", kind=ItemKind.tv, supports_aliases=True, supports_links=True),
        "character": EntityRefSpec("character", "characters", "Character", supports_aliases=True, supports_links=True),
        "story_arc": EntityRefSpec("story_arc", "story_arcs", "Story arc", supports_aliases=True, supports_links=True),
        "organization": EntityRefSpec("organization", "organizations", "Organization", supports_aliases=True, supports_links=True),
        "person": EntityRefSpec("person", "persons", "Person", supports_aliases=True, supports_links=True),
        "tag": EntityRefSpec("tag", "tags", "Tag", supports_aliases=True, supports_links=True),
    }
)
