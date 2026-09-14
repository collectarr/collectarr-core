from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import (
    MusicMediumV1Response,
    MusicReleaseGroupV1Response,
    MusicReleaseV1Response,
    MusicTrackV1Response,
)
from app.services.facade import MetadataFacade as MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/music/release-groups/{group_id}", response_model=MusicReleaseGroupV1Response)
async def get_music_release_group(group_id: UUID, db: DbSession) -> MusicReleaseGroupV1Response:
    return await MetadataService(db).get_music_release_group(group_id)


@router.get("/metadata/music/releases/{release_id}", response_model=MusicReleaseV1Response)
async def get_music_release(release_id: UUID, db: DbSession) -> MusicReleaseV1Response:
    return await MetadataService(db).get_music_release(release_id)


@router.get(
    "/metadata/music/releases/{release_id}/mediums",
    response_model=list[MusicMediumV1Response],
)
async def get_music_release_mediums(
    release_id: UUID,
    db: DbSession,
) -> list[MusicMediumV1Response]:
    return await MetadataService(db).get_music_release_mediums(release_id)


@router.get("/metadata/music/mediums/{medium_id}", response_model=MusicMediumV1Response)
async def get_music_medium(medium_id: UUID, db: DbSession) -> MusicMediumV1Response:
    return await MetadataService(db).get_music_medium(medium_id)


@router.get(
    "/metadata/music/mediums/{medium_id}/tracks",
    response_model=list[MusicTrackV1Response],
)
async def get_music_medium_tracks(
    medium_id: UUID,
    db: DbSession,
) -> list[MusicTrackV1Response]:
    return await MetadataService(db).get_music_medium_tracks(medium_id)


@router.get("/metadata/music/tracks/{track_id}", response_model=MusicTrackV1Response)
async def get_music_track(track_id: UUID, db: DbSession) -> MusicTrackV1Response:
    return await MetadataService(db).get_music_track(track_id)
