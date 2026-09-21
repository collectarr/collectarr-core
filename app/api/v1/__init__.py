"""Canonical versioned API composition root."""

from fastapi import APIRouter

from app.api.routes import admin, auth, images, metadata, system

API_V1_PREFIX = "/api/v1"

router = APIRouter(prefix=API_V1_PREFIX)
router.include_router(system.router)
router.include_router(auth.router)
router.include_router(images.router)
router.include_router(metadata.router)
router.include_router(admin.router)
