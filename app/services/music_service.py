from __future__ import annotations

from sqlalchemy import extract, or_, select
from sqlalchemy.orm import selectinload

from app.models import (
    MusicMedium,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseGroup,
    MusicReleaseIdentifier,
)
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult


class MusicService:
    """Searches and barcode resolution at Music's release-group boundary."""

    def _music_search_result(
        self,
        group: MusicReleaseGroup,
        release: MusicRelease | None = None,
    ) -> SearchResult:
        releases = sorted(
            group.releases or [],
            key=lambda row: (row.release_date is None, row.release_date, row.title.casefold()),
        )
        selected = release or (releases[0] if releases else None)
        mediums = (
            sorted(selected.mediums or [], key=lambda row: (row.medium_number, str(row.id)))
            if selected is not None
            else []
        )
        primary = mediums[0] if mediums else None
        tracks = (
            [
                {
                    "id": track.id,
                    "medium_id": track.medium_id,
                    "position": track.position,
                    "title": track.title,
                    "duration_ms": track.duration_ms,
                    "instrument": track.instrument,
                    "composition": track.composition,
                }
                for track in sorted(
                    primary.tracks or [],
                    key=lambda row: (row.position.casefold(), str(row.id)),
                )
            ]
            if primary is not None
            else []
        )
        date_value = group.original_release_date or (selected.release_date if selected else None)
        return SearchResult(
            id=group.id,
            kind=ItemKind.music,
            title=group.title,
            synopsis=group.synopsis,
            cover_image_url=group.cover_image_url or (selected.cover_image_url if selected else None),
            release_date=date_value,
            release_year=date_value.year if date_value else None,
            barcode=(selected.barcode or selected.upc) if selected else None,
            catalog_number=selected.catalog_number if selected else None,
            publisher=selected.publisher if selected else None,
            country=selected.country_code if selected else None,
            language=selected.language if selected else None,
            release_status=selected.release_status if selected else None,
            track_count=sum(medium.track_count or len(medium.tracks or []) for medium in mediums),
            tracks=tracks or None,
            item_number=primary.title if primary is not None else None,
            edition_title=selected.title if selected else None,
        )

    def _music_options(self):
        return (
            selectinload(MusicReleaseGroup.releases)
            .selectinload(MusicRelease.mediums)
            .selectinload(MusicMedium.tracks),
            selectinload(MusicReleaseGroup.releases)
            .selectinload(MusicRelease.contributions)
            .selectinload(MusicReleaseContribution.person),
            selectinload(MusicReleaseGroup.releases).selectinload(MusicRelease.identifiers),
        )

    async def _music_release_by_barcode(self, barcode: str) -> MusicReleaseGroup | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(MusicReleaseGroup)
            .join(MusicReleaseGroup.releases)
            .join(MusicRelease.identifiers, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(MusicReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MusicReleaseIdentifier.normalized_value) == normalized,
                    self._normalized_barcode_expr(MusicRelease.barcode) == normalized,
                    self._normalized_barcode_expr(MusicRelease.upc) == normalized,
                    self._normalized_barcode_expr(MusicRelease.catalog_number) == normalized,
                )
            )
            .options(*self._music_options())
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
            select(MusicReleaseGroup)
            .join(MusicReleaseGroup.releases, isouter=True)
            .options(*self._music_options())
            .order_by(MusicReleaseGroup.sort_title.asc().nullslast(), MusicReleaseGroup.title.asc())
            .distinct()
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    MusicReleaseGroup.title.ilike(pattern),
                    MusicReleaseGroup.artist.ilike(pattern),
                    MusicReleaseGroup.synopsis.ilike(pattern),
                    MusicRelease.title.ilike(pattern),
                    MusicRelease.subtitle.ilike(pattern),
                    MusicRelease.publisher.ilike(pattern),
                    MusicRelease.catalog_number.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(MusicRelease.publisher.ilike(f"%{publisher.strip()}%"))
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
                    self._normalized_barcode_expr(MusicRelease.upc) == normalized,
                    self._normalized_barcode_expr(MusicRelease.catalog_number) == normalized,
                )
            )
        groups = list((await self.db.execute(stmt)).scalars().unique())
        return [self._music_search_result(group) for group in groups]
