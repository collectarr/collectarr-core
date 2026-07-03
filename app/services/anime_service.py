from __future__ import annotations

from datetime import date

from sqlalchemy import extract, or_, select
from sqlalchemy.orm import selectinload

from app.models import AnimeCharacterAppearance, AnimeContribution, AnimeEpisode, AnimeIdentifier, AnimeSeries
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult


class AnimeService:
    def _anime_search_result(self, series: AnimeSeries) -> SearchResult:
        episodes = sorted(
            series.episodes or [],
            key=lambda row: (
                row.episode_number is None,
                row.episode_number or 0,
                row.air_date is None,
                row.air_date or date.max,
                str(row.id),
            ),
        )
        primary = episodes[0] if episodes else None
        return SearchResult(
            id=series.id,
            kind=ItemKind.anime,
            title=series.title,
            synopsis=series.description,
            cover_image_url=primary.cover_image_url if primary is not None else None,
            release_date=series.original_air_date or (primary.air_date if primary is not None else None),
            release_year=(
                (series.original_air_date or primary.air_date).year
                if series.original_air_date or (primary is not None and primary.air_date is not None)
                else None
            ),
            release_status=series.status,
            language=series.original_language,
            item_number=primary.episode_title if primary is not None else None,
            episode_count=series.episode_count,
            series_title=series.title,
        )

    async def _anime_series_by_barcode(self, barcode: str) -> AnimeSeries | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(AnimeSeries)
            .join(AnimeSeries.identifiers, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(AnimeIdentifier.value) == normalized,
                    self._normalized_barcode_expr(AnimeIdentifier.normalized_value) == normalized,
                )
            )
            .options(
                selectinload(AnimeSeries.episodes),
                selectinload(AnimeSeries.contributions).selectinload(AnimeContribution.person),
                selectinload(AnimeSeries.identifiers),
                selectinload(AnimeSeries.character_appearances).selectinload(AnimeCharacterAppearance.character),
            )
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_anime_series(
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
            select(AnimeSeries)
            .options(
                selectinload(AnimeSeries.episodes),
                selectinload(AnimeSeries.contributions).selectinload(AnimeContribution.person),
                selectinload(AnimeSeries.identifiers),
                selectinload(AnimeSeries.character_appearances).selectinload(AnimeCharacterAppearance.character),
            )
            .order_by(AnimeSeries.sort_title.asc().nullslast(), AnimeSeries.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(AnimeSeries.episodes, isouter=True).where(
                or_(
                    AnimeSeries.title.ilike(pattern),
                    AnimeSeries.description.ilike(pattern),
                    AnimeSeries.status.ilike(pattern),
                    AnimeSeries.anime_type.ilike(pattern),
                    AnimeEpisode.episode_title.ilike(pattern),
                )
            )
        if language and language.strip():
            stmt = stmt.where(AnimeSeries.original_language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(AnimeSeries.status.ilike(f"%{country.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(AnimeSeries.status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", AnimeSeries.original_air_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(AnimeSeries.identifiers, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(AnimeIdentifier.value) == normalized,
                    self._normalized_barcode_expr(AnimeIdentifier.normalized_value) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._anime_search_result(series) for series in rows]
