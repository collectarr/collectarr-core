from __future__ import annotations

from fastapi import APIRouter

from . import (
    anime,
    boardgames,
    books,
    browse,
    comics,
    corrections,
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
legacy_router = APIRouter(tags=["metadata"])
router.include_router(field_schema.router)
router.include_router(corrections.router)
for child_router in (
    field_schema.router,
    search.router,
    proposals.router,
    submissions.router,
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
    legacy_router.include_router(child_router)
    if child_router is not field_schema.router:
        router.include_router(child_router)
