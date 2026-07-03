from __future__ import annotations

from datetime import date

from sqlalchemy import extract, or_, select
from sqlalchemy.orm import selectinload

from app.models import MovieRelease, MovieWork, MovieWorkContribution, MovieWorkIdentifier
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult


class MoviesService:
    async def _search_movie_works(
        self,
        *,
        query: str | None,
        publisher: str | None,
        subtitle: str | None,
        language: str | None,
        country: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(MovieWork)
            .options(
                selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
                selectinload(MovieWork.releases).selectinload(MovieRelease.media),
                selectinload(MovieWork.identifiers),
            )
            .order_by(MovieWork.sort_title.asc().nullslast(), MovieWork.title.asc())
            .limit(limit)
        )
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        if pattern:
            stmt = stmt.where(
                or_(
                    MovieWork.title.ilike(pattern),
                    MovieWork.subtitle.ilike(pattern),
                    MovieRelease.distributor.ilike(pattern),
                    MovieRelease.publisher.ilike(pattern),
                    MovieRelease.format.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(
                or_(
                    MovieRelease.publisher.ilike(f"%{publisher.strip()}%"),
                    MovieRelease.distributor.ilike(f"%{publisher.strip()}%"),
                )
            )
        if subtitle and subtitle.strip():
            stmt = stmt.where(MovieWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(
                or_(MovieRelease.language_audio.any(language.strip()), MovieRelease.language_subtitles.any(language.strip()))
            )
        if country and country.strip():
            stmt = stmt.where(MovieRelease.region_code.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(MovieWork.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(
                or_(
                    MovieRelease.sku.ilike(f"%{catalog_number.strip()}%"),
                    MovieRelease.barcode.ilike(f"%{catalog_number.strip()}%"),
                )
            )
        if release_status and release_status.strip():
            stmt = stmt.where(MovieRelease.release_type.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", MovieRelease.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(MovieWorkIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MovieRelease.barcode) == normalized,
                    self._normalized_barcode_expr(MovieRelease.sku) == normalized,
                )
            )
        rows = list(
            (
                await self.db.execute(
                    stmt.join(MovieWork.releases, isouter=True).join(MovieWork.identifiers, isouter=True)
                )
            )
            .scalars()
            .unique()
        )
        return [self._movie_search_result(work) for work in rows]

    def _movie_search_result(self, work: MovieWork, *, release: MovieRelease | None = None) -> SearchResult:
        releases = sorted(
            work.releases or [],
            key=lambda row: (
                row.release_date is None,
                row.release_date or date.max,
                str(row.id),
            ),
        )
        primary = release or (releases[0] if releases else None)
        return SearchResult(
            id=work.id,
            kind=ItemKind.movie,
            title=work.title,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else work.poster_image_url,
            thumbnail_image_url=None,
            edition_title=primary.format if primary is not None else None,
            physical_format=primary.format if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            release_date=primary.release_date if primary is not None else work.original_release_date,
            release_year=(primary.release_date or work.original_release_date).year
            if (primary is not None and primary.release_date is not None) or work.original_release_date is not None
            else None,
            barcode=primary.barcode if primary is not None and primary.barcode else primary.sku if primary is not None else None,
            release_status=primary.release_type if primary is not None else work.status,
            language=next(iter(primary.language_audio), None) if primary is not None and primary.language_audio else None,
            age_rating=work.age_rating,
            creators=[
                {"name": row.person.name, "role": row.role}
                for row in sorted(
                    work.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
                if row.person is not None
            ],
            catalog_number=primary.sku if primary is not None else None,
            country=primary.region_code if primary is not None else None,
        )

    async def _movie_work_by_barcode(self, barcode: str) -> tuple[MovieWork, MovieRelease | None] | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        row = (
            await self.db.execute(
                select(MovieWork, MovieRelease)
                .join(MovieWork.releases, isouter=True)
                .join(MovieWork.identifiers, isouter=True)
                .where(
                    or_(
                        self._normalized_barcode_expr(MovieWorkIdentifier.value) == normalized,
                        self._normalized_barcode_expr(MovieRelease.barcode) == normalized,
                        self._normalized_barcode_expr(MovieRelease.sku) == normalized,
                    )
                )
                .options(
                    selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
                    selectinload(MovieWork.releases).selectinload(MovieRelease.media),
                    selectinload(MovieWork.identifiers),
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]
