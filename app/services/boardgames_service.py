from __future__ import annotations

from datetime import date

from sqlalchemy import extract, or_, select
from sqlalchemy.orm import selectinload

from app.models import BoardGameEdition, BoardGameWork
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult


class BoardGamesService:
    def _boardgame_search_result(self, work: BoardGameWork) -> SearchResult:
        editions = sorted(
            work.editions or [],
            key=lambda row: (
                row.release_date is None,
                row.release_date or date.max,
                str(row.id),
            ),
        )
        primary = editions[0] if editions else None
        return SearchResult(
            id=work.id,
            kind=ItemKind.boardgame,
            title=work.title,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else work.cover_image_url,
            release_date=primary.release_date if primary is not None else None,
            release_year=primary.release_date.year if primary is not None and primary.release_date else None,
            barcode=primary.barcode if primary is not None else None,
            catalog_number=primary.catalog_number if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            country=primary.country if primary is not None else None,
            language=primary.language if primary is not None else None,
            age_rating=primary.age_rating if primary is not None else work.age_rating,
            release_status=primary.release_status if primary is not None else None,
            item_number=primary.edition_title if primary is not None else None,
            edition_title=primary.edition_title if primary is not None else None,
        )

    async def _boardgame_work_by_barcode(self, barcode: str) -> BoardGameWork | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(BoardGameWork)
            .join(BoardGameWork.editions, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(BoardGameEdition.barcode) == normalized,
                    self._normalized_barcode_expr(BoardGameEdition.catalog_number) == normalized,
                )
            )
            .options(selectinload(BoardGameWork.editions))
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_boardgame_works(
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
            select(BoardGameWork)
            .options(selectinload(BoardGameWork.editions))
            .order_by(BoardGameWork.sort_title.asc().nullslast(), BoardGameWork.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(BoardGameWork.editions, isouter=True).where(
                or_(
                    BoardGameWork.title.ilike(pattern),
                    BoardGameWork.subtitle.ilike(pattern),
                    BoardGameEdition.publisher.ilike(pattern),
                    BoardGameEdition.catalog_number.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(BoardGameEdition.publisher.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(BoardGameWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(BoardGameEdition.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(BoardGameEdition.country.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(BoardGameEdition.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(BoardGameEdition.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(BoardGameEdition.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", BoardGameEdition.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(BoardGameWork.editions, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(BoardGameEdition.barcode) == normalized,
                    self._normalized_barcode_expr(BoardGameEdition.catalog_number) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._boardgame_search_result(work) for work in rows]
