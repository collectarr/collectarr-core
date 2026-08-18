from __future__ import annotations

from fastapi import APIRouter

from . import (
    anime,
    boardgames,
    books,
    browse,
    comics,
    field_schema,
    games,
    manga,
    movies,
    music,
    proposals,
    search,
    submissions,
    tv,
)

router = APIRouter(tags=["metadata"])
router.include_router(field_schema.router)
router.include_router(search.router)
router.include_router(proposals.router)
router.include_router(submissions.router)
router.include_router(browse.router)
router.include_router(books.router)
router.include_router(comics.router)
router.include_router(manga.router)
router.include_router(anime.router)
router.include_router(movies.router)
router.include_router(tv.router)
router.include_router(games.router)
router.include_router(boardgames.router)
router.include_router(music.router)
