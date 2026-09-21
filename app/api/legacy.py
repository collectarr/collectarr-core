"""Explicit aliases for the pre-v1 route surface.

New endpoints must not be added here. This router exists only so existing
clients can migrate to :mod:`app.api.v1` without changing behavior in place.
"""

from fastapi import APIRouter

from app.api.routes import admin, auth, images, metadata, system

router = APIRouter()
router.include_router(system.router)
router.include_router(auth.router)
router.include_router(images.router)
router.include_router(metadata.legacy_router)
router.include_router(admin.router)
