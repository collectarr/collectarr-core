from __future__ import annotations

from fastapi import APIRouter

from . import (
    browse,
    catalog_anime_items,
    catalog_boardgame_items,
    catalog_book_items,
    catalog_comic_items,
    catalog_game_items,
    catalog_manga_items,
    catalog_movie_items,
    catalog_music_items,
    catalog_tv_items,
    corrections,
    field_schema,
    proposals,
    search,
)

router = APIRouter(tags=["metadata"])
router.include_router(field_schema.router)
router.include_router(corrections.router)
for child_router in (
    field_schema.router,
    search.router,
    proposals.router,
    catalog_boardgame_items.router,
    catalog_book_items.router,
    catalog_comic_items.router,
    catalog_anime_items.router,
    catalog_game_items.router,
    catalog_manga_items.router,
    catalog_movie_items.router,
    catalog_music_items.router,
    catalog_tv_items.router,
    browse.router,
):
    if child_router is not field_schema.router:
        router.include_router(child_router)
