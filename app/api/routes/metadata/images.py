from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.deps import DbSession
from app.api.routes.metadata_images import gcd_provider_image, mangadex_provider_image

router = APIRouter(tags=["metadata"])


@router.get("/metadata/providers/gcd/images/{provider_item_id}")
async def gcd_provider_image_route(
    provider_item_id: str,
    db: DbSession,
    series: str | None = None,
    issue: str | None = None,
    year: int | None = None,
    variant: str | None = None,
) -> Response:
    return await gcd_provider_image(
        db,
        provider_item_id,
        series=series,
        issue=issue,
        year=year,
        variant=variant,
    )


@router.get("/metadata/providers/mangadex/images/{provider_item_id}")
async def mangadex_provider_image_route(
    provider_item_id: str,
    db: DbSession,
) -> Response:
    return await mangadex_provider_image(db, provider_item_id)
