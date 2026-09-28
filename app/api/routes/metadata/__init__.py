from __future__ import annotations

from fastapi import APIRouter

from . import catalog_items, corrections, field_schema

router = APIRouter(tags=["metadata"])
router.include_router(field_schema.router)
router.include_router(corrections.router)
router.include_router(catalog_items.router)
