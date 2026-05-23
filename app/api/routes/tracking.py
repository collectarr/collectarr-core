from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models.base import ItemKind
from app.schemas.tracking import (
    TrackingDashboardResponse,
    TrackingEntryResponse,
    TrackingEntryUpsertRequest,
    TrackingFacetsResponse,
    TrackingItemStatsResponse,
)
from app.services.tracking import TrackingService

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.get("/entries", response_model=list[TrackingEntryResponse])
async def list_tracking_entries(
    db: DbSession,
    user: CurrentUser,
    kind: ItemKind | None = None,
    status_filter: str | None = Query(default=None, alias="status", min_length=1, max_length=64),
    source_type: str | None = Query(default=None, min_length=1, max_length=64),
    item_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[TrackingEntryResponse]:
    return await TrackingService(db).list_entries(
        user,
        kind=kind,
        status_filter=status_filter,
        source_type=source_type,
        item_id=item_id,
        limit=limit,
    )


@router.get("/entries/{entry_id}", response_model=TrackingEntryResponse)
async def get_tracking_entry(entry_id: UUID, db: DbSession, user: CurrentUser) -> TrackingEntryResponse:
    return await TrackingService(db).get_entry(user, entry_id)


@router.post("/entries", response_model=TrackingEntryResponse)
async def upsert_tracking_entry(
    payload: TrackingEntryUpsertRequest,
    db: DbSession,
    user: CurrentUser,
) -> TrackingEntryResponse:
    return await TrackingService(db).upsert_entry(user, payload)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracking_entry(entry_id: UUID, db: DbSession, user: CurrentUser) -> Response:
    await TrackingService(db).delete_entry(user, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/items/{item_id}/stats", response_model=TrackingItemStatsResponse)
async def tracking_item_stats(item_id: UUID, db: DbSession, user: CurrentUser) -> TrackingItemStatsResponse:
    return await TrackingService(db).item_stats(user, item_id)


@router.get("/dashboard", response_model=TrackingDashboardResponse)
async def tracking_dashboard(
    db: DbSession,
    user: CurrentUser,
    kind: ItemKind | None = None,
    status_filter: str | None = Query(default=None, alias="status", min_length=1, max_length=64),
    source_type: str | None = Query(default=None, min_length=1, max_length=64),
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
) -> TrackingDashboardResponse:
    return await TrackingService(db).dashboard(
        user,
        kind=kind,
        status_filter=status_filter,
        source_type=source_type,
        updated_from=updated_from,
        updated_to=updated_to,
    )


@router.get("/dashboard/facets", response_model=TrackingFacetsResponse)
async def tracking_dashboard_facets(
    db: DbSession,
    user: CurrentUser,
    kind: ItemKind | None = None,
    status_filter: str | None = Query(default=None, alias="status", min_length=1, max_length=64),
    source_type: str | None = Query(default=None, min_length=1, max_length=64),
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
) -> TrackingFacetsResponse:
    return await TrackingService(db).dashboard_facets(
        user,
        kind=kind,
        status_filter=status_filter,
        source_type=source_type,
        updated_from=updated_from,
        updated_to=updated_to,
    )