from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import MovieReleaseV1Response, MovieWorkV1Response
from app.services.metadata import MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/movies/works/{work_id}", response_model=MovieWorkV1Response)
async def get_movie_work(work_id: UUID, db: DbSession) -> MovieWorkV1Response:
    return await MetadataService(db).get_movie_work(work_id)


@router.get(
    "/metadata/movies/works/{work_id}/releases",
    response_model=list[MovieReleaseV1Response],
)
async def get_movie_work_releases(
    work_id: UUID,
    db: DbSession,
) -> list[MovieReleaseV1Response]:
    return await MetadataService(db).get_movie_work_releases(work_id)


@router.get("/metadata/movies/releases/{release_id}", response_model=MovieReleaseV1Response)
async def get_movie_release(release_id: UUID, db: DbSession) -> MovieReleaseV1Response:
    return await MetadataService(db).get_movie_release(release_id)
