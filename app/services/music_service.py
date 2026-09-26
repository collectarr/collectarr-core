from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Text, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ApiHTTPException
from app.models import EntityLink, MusicAlbum, MusicAlbumCredit, MusicAlbumDiscTitle, MusicAlbumTrack
from app.models.base import ItemKind
from app.models.partial_date import PartialDateValue, partial_date_from_storage
from app.schemas.metadata_music import (
    MusicAlbumCreditV1,
    MusicAlbumDiscTitleV1,
    MusicAlbumLinkV1,
    MusicAlbumTrackV1,
    MusicAlbumV1Response,
    MusicAlbumWriteV1,
)
from app.schemas.metadata_shared import SearchResult


class MusicService:
    """Read, search, and write the source-neutral MusicAlbum catalog."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_album(self, album_id: UUID) -> MusicAlbumV1Response:
        album = await self._load_album(album_id)
        if album is None:
            raise ApiHTTPException(
                status_code=404,
                code="music_album_not_found",
                detail=f"Music album {album_id} was not found.",
            )
        return self._response(album)

    async def search_albums(
        self,
        *,
        query: str | None = None,
        barcode: str | None = None,
        catalog_number: str | None = None,
        limit: int = 50,
    ) -> list[SearchResult]:
        stmt = select(MusicAlbum).options(selectinload(MusicAlbum.tracks)).order_by(
            MusicAlbum.sort_title.asc().nullslast(), MusicAlbum.title.asc(), MusicAlbum.id.asc()
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    MusicAlbum.title.ilike(pattern),
                    MusicAlbum.sort_title.ilike(pattern),
                    MusicAlbum.subtitle.ilike(pattern),
                    cast(MusicAlbum.artists, Text).ilike(pattern),
                    cast(MusicAlbum.labels, Text).ilike(pattern),
                    cast(MusicAlbum.genres, Text).ilike(pattern),
                )
            )
        if barcode and barcode.strip():
            normalized = self._normalize_identifier(barcode)
            normalized_column = func.lower(
                func.replace(
                    func.replace(func.replace(MusicAlbum.barcode, "-", ""), " ", ""),
                    ".",
                    "",
                )
            )
            stmt = stmt.where(normalized_column == normalized)
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(MusicAlbum.catalog_number.ilike(f"%{catalog_number.strip()}%"))

        rows = list((await self.db.execute(stmt.limit(max(1, min(limit, 200))))).scalars())
        return [self._search_result(row) for row in rows]

    async def create_album(self, payload: MusicAlbumWriteV1) -> MusicAlbumV1Response:
        album = MusicAlbum(id=uuid4(), title=payload.title.strip())
        await self._apply_write(album, payload)
        self.db.add(album)
        await self.db.flush()
        await self.db.commit()
        loaded = await self._load_album(album.id)
        assert loaded is not None
        return self._response(loaded)

    async def update_album(self, album_id: UUID, payload: MusicAlbumWriteV1) -> MusicAlbumV1Response:
        album = await self._load_album(album_id, lock=True)
        if album is None:
            raise ApiHTTPException(
                status_code=404,
                code="music_album_not_found",
                detail=f"Music album {album_id} was not found.",
            )
        await self._apply_write(album, payload)
        await self.db.flush()
        await self.db.commit()
        loaded = await self._load_album(album_id)
        assert loaded is not None
        return self._response(loaded)

    async def _load_album(self, album_id: UUID, *, lock: bool = False) -> MusicAlbum | None:
        stmt = (
            select(MusicAlbum)
            .where(MusicAlbum.id == album_id)
            .options(
                selectinload(MusicAlbum.tracks),
                selectinload(MusicAlbum.disc_titles),
                selectinload(MusicAlbum.credits),
                selectinload(MusicAlbum.links),
            )
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.db.scalar(stmt)

    async def _apply_write(self, album: MusicAlbum, payload: MusicAlbumWriteV1) -> None:
        album.title = payload.title.strip()
        album.sort_title = payload.sort_title
        album.subtitle = payload.subtitle
        album.artists = [item.model_dump() for item in payload.artists]
        album.release_date, album.release_date_parts = self._stored_date(payload.release_date)
        album.original_release_date, album.original_release_date_parts = self._stored_date(
            payload.original_release_date
        )
        album.recording_date, album.recording_date_parts = self._stored_date(payload.recording_date)
        album.labels = [item.model_dump() for item in payload.labels]
        album.format = payload.format
        album.barcode = payload.barcode
        album.catalog_number = payload.catalog_number
        album.genres = list(payload.genres)
        album.packaging = payload.packaging
        album.studio = list(payload.studio)
        album.country = payload.country
        album.is_live = payload.is_live
        album.sound_types = list(payload.sound_types)
        album.vinyl_color = payload.vinyl_color
        album.vinyl_weight = float(payload.vinyl_weight) if payload.vinyl_weight is not None else None
        album.rpm = payload.rpm
        album.extras = list(payload.extras)
        album.spars_code = payload.spars_code
        album.box_set = payload.box_set
        album.matrix_number_side_a = payload.matrix_number_side_a
        album.matrix_number_side_b = payload.matrix_number_side_b
        album.cover_image_url = str(payload.cover_image_url) if payload.cover_image_url else None
        album.back_cover_image_url = (
            str(payload.back_cover_image_url) if payload.back_cover_image_url else None
        )
        album.disc_titles = [
            MusicAlbumDiscTitle(disc_number=item.disc_number, title=item.title.strip())
            for item in payload.disc_titles
        ]
        album.tracks = [
            MusicAlbumTrack(
                album_id=album.id,
                disc_number=item.disc_number,
                position=item.position,
                title=item.title.strip(),
                artist=item.artist,
                duration_ms=item.duration_ms,
            )
            for item in payload.tracks
        ]
        album.credits = []
        for item in payload.credits:
            values = item.model_dump()
            values["credited_name"] = item.credited_name.strip()
            album.credits.append(MusicAlbumCredit(**values))

        link_rows = [
            EntityLink(
                entity_type="music_album",
                entity_id=album.id,
                link_type="external",
                url=str(item.url),
                name=item.title,
                description=item.description,
                position=item.position,
            )
            for item in payload.links
        ]
        await self.db.execute(
            delete(EntityLink).where(
                EntityLink.entity_type == "music_album", EntityLink.entity_id == album.id
            )
        )
        self.db.add_all(link_rows)

    @staticmethod
    def _stored_date(value: PartialDateValue | None) -> tuple[date | None, str | None]:
        if value is None:
            return None, None
        return value.as_date, value.json_value()

    def _response(self, album: MusicAlbum) -> MusicAlbumV1Response:
        return MusicAlbumV1Response(
            id=album.id,
            title=album.title,
            sort_title=album.sort_title,
            subtitle=album.subtitle,
            artists=album.artists,
            release_date=self._partial_date(album.release_date, album.release_date_parts),
            original_release_date=self._partial_date(
                album.original_release_date, album.original_release_date_parts
            ),
            recording_date=self._partial_date(album.recording_date, album.recording_date_parts),
            labels=album.labels,
            format=album.format,
            barcode=album.barcode,
            catalog_number=album.catalog_number,
            genres=album.genres,
            packaging=album.packaging,
            studio=album.studio,
            country=album.country,
            is_live=album.is_live,
            sound_types=album.sound_types,
            vinyl_color=album.vinyl_color,
            vinyl_weight=Decimal(str(album.vinyl_weight)) if album.vinyl_weight is not None else None,
            rpm=album.rpm,
            extras=album.extras,
            spars_code=album.spars_code,
            box_set=album.box_set,
            matrix_number_side_a=album.matrix_number_side_a,
            matrix_number_side_b=album.matrix_number_side_b,
            cover_image_url=album.cover_image_url,
            back_cover_image_url=album.back_cover_image_url,
            disc_titles=[
                MusicAlbumDiscTitleV1.model_validate(item, from_attributes=True)
                for item in album.disc_titles
            ],
            tracks=[
                MusicAlbumTrackV1(
                    album_id=item.album_id,
                    disc_number=item.disc_number,
                    position=item.position,
                    title=item.title,
                    artist=item.artist,
                    duration_ms=item.duration_ms,
                )
                for item in album.tracks
            ],
            credits=[MusicAlbumCreditV1.model_validate(item, from_attributes=True) for item in album.credits],
            links=[
                MusicAlbumLinkV1(
                    position=item.position,
                    url=item.url,
                    title=item.name,
                    description=item.description,
                )
                for item in album.links
            ],
            created_at=album.created_at,
            updated_at=album.updated_at,
        )

    @staticmethod
    def _partial_date(value: date | None, parts: str | None) -> PartialDateValue | None:
        parsed = partial_date_from_storage(parts)
        if parsed is not None:
            return parsed
        return PartialDateValue.model_validate(value) if value is not None else None

    @staticmethod
    def _search_result(album: MusicAlbum) -> SearchResult:
        artist = album.artists[0].get("name") if album.artists else None
        release_date = album.release_date
        return SearchResult(
            id=album.id,
            kind=ItemKind.music,
            title=album.title,
            subtitle=album.subtitle,
            cover_image_url=album.cover_image_url,
            edition_title=album.title,
            physical_format=album.format,
            artist=artist,
            release_date=release_date,
            release_date_parts=MusicService._partial_date(
                release_date, album.release_date_parts
            ),
            release_year=release_date.year if release_date else None,
            barcode=album.barcode,
            catalog_number=album.catalog_number,
            creators=[{"name": entry.get("name")} for entry in album.artists],
            genres=album.genres,
            country=album.country,
            track_count=len(album.tracks),
            tracks=[
                {
                    "album_id": str(track.album_id),
                    "disc_number": track.disc_number,
                    "position": track.position,
                    "title": track.title,
                    "artist": track.artist,
                    "duration_ms": track.duration_ms,
                }
                for track in sorted(album.tracks, key=lambda row: (row.disc_number, row.position))
            ],
        )

    @staticmethod
    def _normalize_identifier(value: str) -> str:
        return "".join(character for character in value if character.isalnum()).casefold()
