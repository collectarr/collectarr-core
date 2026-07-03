from __future__ import annotations

from datetime import date

from sqlalchemy import extract, or_, select
from sqlalchemy.orm import selectinload

from app.models import (
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaIdentifier,
    MangaSeriesMembership,
    MangaWork,
)
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult


class MangaService:
    def _manga_search_result(self, work: MangaWork) -> SearchResult:
        chapters = sorted(
            work.chapters or [],
            key=lambda row: (
                row.chapter_number is None,
                row.chapter_number or 0,
                row.publication_date is None,
                row.publication_date or date.max,
                str(row.id),
            ),
        )
        primary = chapters[0] if chapters else None
        return SearchResult(
            id=work.id,
            kind=ItemKind.manga,
            title=work.title,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else None,
            release_date=work.original_publication_date or (primary.publication_date if primary is not None else None),
            release_year=(
                (work.original_publication_date or primary.publication_date).year
                if work.original_publication_date or (primary is not None and primary.publication_date is not None)
                else None
            ),
            release_status=work.status,
            item_number=primary.chapter_title if primary is not None else None,
            series_title=work.title,
            volume_name=work.title,
            page_count=primary.page_count if primary is not None else None,
        )

    async def _manga_work_by_barcode(self, barcode: str) -> MangaWork | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(MangaWork)
            .join(MangaWork.identifiers, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(MangaIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MangaIdentifier.normalized_value) == normalized,
                )
            )
            .options(
                selectinload(MangaWork.chapters),
                selectinload(MangaWork.contributions).selectinload(MangaContribution.person),
                selectinload(MangaWork.identifiers),
                selectinload(MangaWork.character_appearances).selectinload(MangaCharacterAppearance.character),
                selectinload(MangaWork.series_memberships).selectinload(MangaSeriesMembership.series),
            )
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_manga_works(
        self,
        *,
        query: str | None,
        language: str | None,
        country: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(MangaWork)
            .options(
                selectinload(MangaWork.chapters),
                selectinload(MangaWork.contributions).selectinload(MangaContribution.person),
                selectinload(MangaWork.identifiers),
                selectinload(MangaWork.character_appearances).selectinload(MangaCharacterAppearance.character),
                selectinload(MangaWork.series_memberships).selectinload(MangaSeriesMembership.series),
            )
            .order_by(MangaWork.sort_title.asc().nullslast(), MangaWork.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(MangaWork.chapters, isouter=True).where(
                or_(
                    MangaWork.title.ilike(pattern),
                    MangaWork.subtitle.ilike(pattern),
                    MangaChapter.chapter_title.ilike(pattern),
                )
            )
        if language and language.strip():
            stmt = stmt.where(MangaWork.original_language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(MangaWork.status.ilike(f"%{country.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(MangaWork.status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", MangaWork.original_publication_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(MangaWork.identifiers, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(MangaIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MangaIdentifier.normalized_value) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._manga_search_result(work) for work in rows]
