from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models import BookContribution, BookEdition, BookIdentifier, BookWork
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult


class BooksService:
    async def _search_book_works(
        self,
        *,
        query: str | None,
        series: str | None,
        publisher: str | None,
        imprint: str | None,
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
            select(BookWork)
            .options(
                selectinload(BookWork.editions).selectinload(BookEdition.contributions).selectinload(
                    BookContribution.person
                ),
                selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
            )
            .order_by(BookWork.sort_title.asc().nullslast(), BookWork.title.asc())
            .limit(limit)
        )
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        if pattern:
            stmt = stmt.where(
                or_(
                    BookWork.title.ilike(pattern),
                    BookWork.subtitle.ilike(pattern),
                    BookEdition.display_title.ilike(pattern),
                    BookEdition.edition_statement.ilike(pattern),
                    BookEdition.publisher.ilike(pattern),
                    BookEdition.imprint.ilike(pattern),
                )
            )
        if series and series.strip():
            stmt = stmt.where(BookWork.title.ilike(f"%{series.strip()}%"))
        if publisher and publisher.strip():
            stmt = stmt.where(BookEdition.publisher.ilike(f"%{publisher.strip()}%"))
        if imprint and imprint.strip():
            stmt = stmt.where(BookEdition.imprint.ilike(f"%{imprint.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(BookWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(BookEdition.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(BookEdition.region.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(BookEdition.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(BookEdition.edition_statement.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(BookEdition.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(func.extract("year", BookEdition.publication_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(BookIdentifier.value) == normalized,
                    self._normalized_barcode_expr(BookIdentifier.normalized_value) == normalized,
                )
            )
        rows = list(
            (
                await self.db.execute(
                    stmt.join(BookWork.editions, isouter=True).join(BookEdition.identifiers, isouter=True)
                )
            )
            .scalars()
            .unique()
        )
        return [self._book_search_result(work) for work in rows]

    def _book_search_result(self, work: BookWork, *, edition: BookEdition | None = None) -> SearchResult:
        editions = sorted(
            work.editions or [],
            key=lambda row: (
                row.publication_date is None,
                row.publication_date or date.max,
                str(row.id),
            ),
        )
        primary = edition or (editions[0] if editions else None)
        creators: list[dict[str, object]] = []
        if primary is not None:
            for row in primary.contributions or []:
                if row.person is None:
                    continue
                creators.append({"name": row.person.name, "role": row.role})
        return SearchResult(
            id=work.id,
            kind=ItemKind.book,
            title=work.title,
            item_number=primary.display_title if primary is not None else None,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else None,
            edition_title=primary.display_title if primary is not None else None,
            physical_format=primary.format if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            release_date=primary.publication_date if primary is not None else None,
            release_year=primary.publication_date.year if primary is not None and primary.publication_date else None,
            barcode=next((identifier.value for identifier in (primary.identifiers or []) if identifier.value), None)
            if primary is not None
            else None,
            variant=primary.binding if primary is not None else None,
            series_title=work.title,
            volume_name=work.title,
            creators=creators or None,
            page_count=primary.page_count if primary is not None else None,
            country=primary.region if primary is not None else None,
            release_status=primary.release_status if primary is not None else None,
            language=primary.language if primary is not None else None,
            age_rating=primary.age_rating if primary is not None else None,
            imprint=primary.imprint if primary is not None else None,
            subtitle=primary.edition_statement if primary is not None else None,
        )

    async def _book_work_by_barcode(self, barcode: str) -> tuple[BookWork, BookEdition | None] | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        row = (
            await self.db.execute(
                select(BookWork, BookEdition)
                .join(BookWork.editions)
                .join(BookEdition.identifiers)
                .where(
                    or_(
                        self._normalized_barcode_expr(BookIdentifier.value) == normalized,
                        self._normalized_barcode_expr(BookIdentifier.normalized_value) == normalized,
                    )
                )
                .options(
                    selectinload(BookWork.editions).selectinload(BookEdition.contributions).selectinload(
                        BookContribution.person
                    ),
                    selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]
