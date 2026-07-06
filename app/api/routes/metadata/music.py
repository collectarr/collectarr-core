from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas import MusicMediaV1Response, MusicReleaseV1Response, MusicTrackV1Response
from app.services.facade import MetadataFacade as MetadataService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/music/releases/{release_id}", response_model=MusicReleaseV1Response)
async def get_music_release(release_id: UUID, db: DbSession) -> MusicReleaseV1Response:
    return await MetadataService(db).get_music_release(release_id)


@router.get(
    "/metadata/music/releases/{release_id}/media", response_model=list[MusicMediaV1Response]
)
async def get_music_release_media(
    release_id: UUID,
    db: DbSession,
) -> list[MusicMediaV1Response]:
    return await MetadataService(db).get_music_release_media(release_id)


@router.get("/metadata/music/media/{media_id}", response_model=MusicMediaV1Response)
async def get_music_media(media_id: UUID, db: DbSession) -> MusicMediaV1Response:
    return await MetadataService(db).get_music_media(media_id)


@router.get("/metadata/music/media/{media_id}/tracks", response_model=list[MusicTrackV1Response])
async def get_music_media_tracks(
    media_id: UUID,
    db: DbSession,
) -> list[MusicTrackV1Response]:
    return await MetadataService(db).get_music_media_tracks(media_id)


@router.get("/metadata/music/tracks/{track_id}", response_model=MusicTrackV1Response)
async def get_music_track(track_id: UUID, db: DbSession) -> MusicTrackV1Response:
    return await MetadataService(db).get_music_track(track_id)
