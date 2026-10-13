from __future__ import annotations

from fastapi import APIRouter

from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS

from . import browse, corrections, field_schema, proposals, search

router = APIRouter(tags=["metadata"])
router.include_router(field_schema.router)
router.include_router(corrections.router)
router.include_router(search.router)
router.include_router(proposals.router)
for kind_definition in CATALOG_KIND_DEFINITIONS:
    router.include_router(kind_definition.router)
router.include_router(browse.router)
