from __future__ import annotations

import httpx  # noqa: F401
from fastapi import APIRouter

from app.api.routes.metadata_images import (  # noqa: F401
    _download_mangadex_cover,
    gcd_provider_image,
    mangadex_provider_image,
)
from app.core.config import get_settings  # noqa: F401

from . import (
    anime,
    boardgames,
    books,
    browse,
    comics,
    field_schema,
    games,
    images,
    manga,
    movies,
    music,
    proposals,
    providers,
    search,
    tv,
)

router = APIRouter(tags=["metadata"])
router.include_router(field_schema.router)
router.include_router(search.router)
router.include_router(providers.router)
router.include_router(proposals.router)
router.include_router(browse.router)
router.include_router(images.router)
router.include_router(books.router)
router.include_router(comics.router)
router.include_router(manga.router)
router.include_router(anime.router)
router.include_router(movies.router)
router.include_router(tv.router)
router.include_router(games.router)
router.include_router(boardgames.router)
router.include_router(music.router)
