from __future__ import annotations

from datetime import date

from sqlalchemy import extract, or_, select
from sqlalchemy.orm import selectinload

from app.models import GameRelease, GameWork
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult


class GamesService:
    def _game_search_result(self, work: GameWork) -> SearchResult:
        releases = sorted(
            work.releases or [],
            key=lambda row: (
                row.release_date is None,
                row.release_date or date.max,
                str(row.id),
            ),
        )
        primary = releases[0] if releases else None
        return SearchResult(
            id=work.id,
            kind=ItemKind.game,
            title=work.title,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else work.cover_image_url,
            release_date=primary.release_date if primary is not None else work.release_date,
            release_year=(primary.release_date or work.release_date).year
            if primary is not None and (primary.release_date or work.release_date)
            else (work.release_date.year if work.release_date else None),
            barcode=primary.barcode if primary is not None else None,
            catalog_number=primary.catalog_number if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            country=primary.region_code if primary is not None else None,
            language=primary.language if primary is not None else None,
            age_rating=work.age_rating,
            release_status=primary.release_status if primary is not None else None,
            item_number=primary.release_title if primary is not None else None,
            edition_title=primary.release_title if primary is not None else None,
        )

    async def _game_work_by_barcode(self, barcode: str) -> GameWork | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(GameWork)
            .join(GameWork.releases, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(GameRelease.barcode) == normalized,
                    self._normalized_barcode_expr(GameRelease.catalog_number) == normalized,
                )
            )
            .options(selectinload(GameWork.releases))
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_game_works(
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
            select(GameWork)
            .options(selectinload(GameWork.releases))
            .order_by(GameWork.sort_title.asc().nullslast(), GameWork.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(GameWork.releases, isouter=True).where(
                or_(
                    GameWork.title.ilike(pattern),
                    GameWork.subtitle.ilike(pattern),
                    GameRelease.publisher.ilike(pattern),
                    GameRelease.format.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(GameRelease.publisher.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(GameWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(GameRelease.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(GameRelease.region_code.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(GameWork.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(GameRelease.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(GameRelease.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", GameRelease.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(GameWork.releases, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(GameRelease.barcode) == normalized,
                    self._normalized_barcode_expr(GameRelease.catalog_number) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._game_search_result(work) for work in rows]
