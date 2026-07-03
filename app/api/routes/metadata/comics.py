from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import ComicIssueV1Response, ComicWorkV1Response
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/comics/works/{work_id}", response_model=ComicWorkV1Response)
async def get_comic_work(work_id: UUID, db: DbSession) -> ComicWorkV1Response:
    return await MetadataService(db).get_comic_work(work_id)


@router.get("/metadata/comics/works/{work_id}/issues", response_model=list[ComicIssueV1Response])
async def get_comic_work_issues(
    work_id: UUID,
    db: DbSession,
) -> list[ComicIssueV1Response]:
    return await MetadataService(db).get_comic_work_issues(work_id)


@router.get("/metadata/comics/issues/{issue_id}", response_model=ComicIssueV1Response)
async def get_comic_issue(issue_id: UUID, db: DbSession) -> ComicIssueV1Response:
    return await MetadataService(db).get_comic_issue(issue_id)

