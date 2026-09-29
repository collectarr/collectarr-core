from __future__ import annotations

from fastapi import APIRouter

from . import (
    anime,
    boardgames,
    books,
    browse,
    catalog_boardgame_items,
    catalog_book_items,
    catalog_game_items,
    catalog_manga_items,
    catalog_movie_items,
    catalog_music_items,
    comics,
    corrections,
    field_schema,
    games,
    manga,
    movies,
    music,
    proposals,
    search,
    tv,
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
    catalog_game_items.router,
    catalog_manga_items.router,
    catalog_movie_items.router,
    catalog_music_items.router,
    browse.router,
    books.router,
    comics.router,
    manga.router,
    anime.router,
    movies.router,
    tv.router,
    games.router,
    boardgames.router,
    music.router,
):
    if child_router is not field_schema.router:
        router.include_router(child_router)
