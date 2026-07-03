from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import MangaChapterV1Response, MangaWorkV1Response
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/manga/works/{work_id}", response_model=MangaWorkV1Response)
async def get_manga_work(work_id: UUID, db: DbSession) -> MangaWorkV1Response:
    return await MetadataService(db).get_manga_work(work_id)


@router.get(
    "/metadata/manga/works/{work_id}/chapters",
    response_model=list[MangaChapterV1Response],
)
async def get_manga_work_chapters(
    work_id: UUID,
    db: DbSession,
) -> list[MangaChapterV1Response]:
    return await MetadataService(db).get_manga_work_chapters(work_id)


@router.get("/metadata/manga/chapters/{chapter_id}", response_model=MangaChapterV1Response)
async def get_manga_chapter(chapter_id: UUID, db: DbSession) -> MangaChapterV1Response:
    return await MetadataService(db).get_manga_chapter(chapter_id)

