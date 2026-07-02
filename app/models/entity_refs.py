from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityRefRegistry:
    table_by_entity_type: dict[str, str]

    def table_name(self, entity_type: str) -> str | None:
        return self.table_by_entity_type.get(entity_type)

    def is_known(self, entity_type: str) -> bool:
        return entity_type in self.table_by_entity_type


DEFAULT_ENTITY_REF_REGISTRY = EntityRefRegistry(
    {
        "item": "items",
        "bundle_release": "bundle_releases",
        "anime_series": "anime_series",
        "boardgame_work": "boardgame_works",
        "boardgame_edition": "boardgame_editions",
        "book_work": "book_works",
        "book_edition": "book_editions",
        "comic_work": "comic_works",
        "comic_volume": "comic_volumes",
        "comic_issue": "comic_issues",
        "comic_series": "comic_series",
        "game_work": "game_works",
        "game_release": "game_releases",
        "manga_series": "manga_series",
        "manga_work": "manga_works",
        "movie_work": "movie_works",
        "music_release": "music_releases",
        "tv_release": "tv_releases",
        "character": "characters",
        "story_arc": "story_arcs",
        "organization": "organizations",
        "person": "persons",
        "tag": "tags",
    }
)
