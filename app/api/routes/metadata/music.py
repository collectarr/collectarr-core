from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAdmin, DbSession
from app.models.user import User
from app.schemas.metadata_music import MusicAlbumV1Response, MusicAlbumWriteV1
from app.schemas.metadata_shared import SearchResult
from app.services.music_service import MusicService

router = APIRouter(tags=["metadata"])


@router.get("/metadata/music/albums", response_model=list[SearchResult])
async def search_music_albums(
    db: DbSession,
    q: str | None = None,
    barcode: str | None = None,
    catalog_number: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SearchResult]:
    return await MusicService(db).search_albums(
        query=q,
        barcode=barcode,
        catalog_number=catalog_number,
        limit=limit,
    )


@router.get("/metadata/music/albums/{album_id}", response_model=MusicAlbumV1Response)
async def get_music_album(album_id: UUID, db: DbSession) -> MusicAlbumV1Response:
    return await MusicService(db).get_album(album_id)


@router.post("/metadata/music/albums", response_model=MusicAlbumV1Response, status_code=201)
async def create_music_album(
    payload: MusicAlbumWriteV1,
    db: DbSession,
    _user: CurrentAdmin,
) -> MusicAlbumV1Response:
    return await MusicService(db).create_album(payload)


@router.put("/metadata/music/albums/{album_id}", response_model=MusicAlbumV1Response)
async def update_music_album(
    album_id: UUID,
    payload: MusicAlbumWriteV1,
    db: DbSession,
    _user: CurrentAdmin,
) -> MusicAlbumV1Response:
    return await MusicService(db).update_album(album_id, payload)
