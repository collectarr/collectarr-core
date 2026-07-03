from __future__ import annotations

from datetime import date

from sqlalchemy import extract, or_, select
from sqlalchemy.orm import selectinload

from app.models import (
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseIdentifier,
    MusicTrack,
)
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult


class MusicService:
    def _music_search_result(self, release: MusicRelease) -> SearchResult:
        media = sorted(
            release.media or [],
            key=lambda row: (
                row.media_number is None,
                row.media_number or 0,
                str(row.id),
            ),
        )
        primary = media[0] if media else None
        tracks = []
        if primary is not None:
            for track in sorted(primary.tracks or [], key=lambda row: (row.position.casefold(), str(row.id))):
                tracks.append(
                    {
                        "id": track.id,
                        "media_id": track.media_id,
                        "position": track.position,
                        "title": track.title,
                        "duration_ms": track.duration_ms,
                        "instrument": track.instrument,
                        "composition": track.composition,
                    }
                )
        return SearchResult(
            id=release.id,
            kind=ItemKind.music,
            title=release.title,
            synopsis=release.extras,
            cover_image_url=release.cover_image_url,
            release_date=release.release_date,
            release_year=release.release_date.year if release.release_date else None,
            barcode=release.barcode,
            catalog_number=release.catalog_number,
            publisher=release.publisher,
            country=release.country_code,
            language=release.language,
            release_status=release.release_status,
            track_count=release.track_count,
            tracks=tracks or None,
            item_number=primary.title if primary is not None else None,
            edition_title=primary.title if primary is not None else None,
        )

    async def _music_release_by_barcode(self, barcode: str) -> MusicRelease | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(MusicRelease)
            .join(MusicRelease.identifiers, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(MusicReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MusicReleaseIdentifier.normalized_value) == normalized,
                    self._normalized_barcode_expr(MusicRelease.barcode) == normalized,
                    self._normalized_barcode_expr(MusicRelease.catalog_number) == normalized,
                )
            )
            .options(
                selectinload(MusicRelease.media).selectinload(MusicMedia.tracks),
                selectinload(MusicRelease.contributions).selectinload(MusicReleaseContribution.person),
                selectinload(MusicRelease.identifiers),
            )
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_music_releases(
        self,
        *,
        query: str | None,
        publisher: str | None,
        subtitle: str | None,
        language: str | None,
        country: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        catalog_number: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(MusicRelease)
            .options(
                selectinload(MusicRelease.media).selectinload(MusicMedia.tracks),
                selectinload(MusicRelease.contributions).selectinload(MusicReleaseContribution.person),
                selectinload(MusicRelease.identifiers),
            )
            .order_by(MusicRelease.sort_title.asc().nullslast(), MusicRelease.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(MusicRelease.media, isouter=True).where(
                or_(
                    MusicRelease.title.ilike(pattern),
                    MusicRelease.subtitle.ilike(pattern),
                    MusicRelease.publisher.ilike(pattern),
                    MusicRelease.studio.ilike(pattern),
                    MusicMedia.title.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(
                or_(
                    MusicRelease.publisher.ilike(f"%{publisher.strip()}%"),
                    MusicRelease.studio.ilike(f"%{publisher.strip()}%"),
                )
            )
        if subtitle and subtitle.strip():
            stmt = stmt.where(MusicRelease.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(MusicRelease.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(MusicRelease.country_code.ilike(f"%{country.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(MusicRelease.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", MusicRelease.release_date) == year)
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(MusicRelease.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(MusicRelease.identifiers, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(MusicReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MusicReleaseIdentifier.normalized_value) == normalized,
                    self._normalized_barcode_expr(MusicRelease.barcode) == normalized,
                    self._normalized_barcode_expr(MusicRelease.catalog_number) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._music_search_result(release) for release in rows]
