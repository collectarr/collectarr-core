from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.sync import SyncChangeResponse, SyncPullRequest, SyncPullResponse, SyncPushRequest, SyncPushResponse
from app.services.sync import SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/pull", response_model=SyncPullResponse)
async def pull_sync(payload: SyncPullRequest, db: DbSession, user: CurrentUser) -> SyncPullResponse:
    return await SyncService(db).pull(user, payload.since)


@router.post("/push", response_model=SyncPushResponse)
async def push_sync(payload: SyncPushRequest, db: DbSession, user: CurrentUser) -> SyncPushResponse:
    return await SyncService(db).push(user, payload)


@router.get("/changes", response_model=list[SyncChangeResponse])
async def sync_changes(
    db: DbSession, user: CurrentUser, since: datetime | None = Query(default=None)
) -> list[SyncChangeResponse]:
    return await SyncService(db).changes_since(user, since)

