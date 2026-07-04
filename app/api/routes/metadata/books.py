from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import BookEditionV1Response, BookWorkV1Response
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/books/works/{work_id}", response_model=BookWorkV1Response)
async def get_book_work(work_id: UUID, db: DbSession) -> BookWorkV1Response:
    return await MetadataService(db).get_book_work(work_id)


@router.get("/metadata/books/works/{work_id}/editions", response_model=list[BookEditionV1Response])
async def get_book_work_editions(
    work_id: UUID,
    db: DbSession,
) -> list[BookEditionV1Response]:
    return await MetadataService(db).get_book_work_editions(work_id)


@router.get("/metadata/books/editions/{edition_id}", response_model=BookEditionV1Response)
async def get_book_edition(edition_id: UUID, db: DbSession) -> BookEditionV1Response:
    return await MetadataService(db).get_book_edition(edition_id)
