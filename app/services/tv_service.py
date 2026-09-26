from __future__ import annotations

from datetime import date

from fastapi import status
from sqlalchemy import extract, or_, select
from sqlalchemy.orm import selectinload

from app.models import (
    TVRelease,
    TVReleaseContribution,
    TVReleaseIdentifier,
    TVSeason,
    TVSeries,
)
from app.models.base import ItemKind
from app.schemas import EpisodeResponse
from app.schemas import SeasonResponse
from app.schemas.metadata_shared import SearchResult


class TVService:
    async def _search_tv_releases(
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
            select(TVSeries)
            .options(
                selectinload(TVSeries.seasons).selectinload(TVSeason.episodes),
                selectinload(TVSeries.releases).selectinload(TVRelease.contributions).selectinload(
                    TVReleaseContribution.person
                ),
                selectinload(TVSeries.releases).selectinload(TVRelease.identifiers),
            )
            .order_by(TVSeries.sort_title.asc().nullslast(), TVSeries.title.asc())
            .limit(limit)
        )
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        if pattern:
            stmt = stmt.where(
                or_(
                    TVSeries.title.ilike(pattern),
                    TVSeries.overview.ilike(pattern),
                    TVSeries.network.ilike(pattern),
                    TVSeries.status.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(TVSeries.network.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(TVSeries.overview.ilike(f"%{subtitle.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(TVSeries.country.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(TVSeries.status.ilike(f"%{age_rating.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(TVSeries.status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", TVSeries.first_air_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(TVSeries.releases, isouter=True).join(TVRelease.identifiers, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(TVReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(TVRelease.sku) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._tv_search_result(series) for series in rows]

    def _tv_search_result(self, series: TVSeries) -> SearchResult:
        release = next(iter(series.releases or []), None)
        return SearchResult(
            id=series.id,
            kind=ItemKind.tv,
            title=series.title,
            synopsis=series.overview,
            cover_image_url=series.poster_url or (release.cover_image_url if release is not None else None),
            physical_format=release.format if release is not None else None,
            publisher=series.network or (release.publisher if release is not None else None),
            release_date=series.first_air_date or (release.release_date if release is not None else None),
            release_year=(series.first_air_date.year if series.first_air_date else None)
            or (release.release_date.year if release is not None and release.release_date else None),
            barcode=next((identifier.value for identifier in release.identifiers or [] if identifier.value), release.sku)
            if release is not None
            else None,
            catalog_number=release.sku if release is not None else None,
            country=series.country or (release.region_code if release is not None else None),
            age_rating=series.status or (release.content_rating if release is not None else None),
            language=series.original_language or (
                (release.language_audio or [None])[0] if release is not None else None
            ),
            release_status=series.status or (release.format if release is not None else None),
        )

    async def _tv_release_by_barcode(self, barcode: str) -> TVSeries | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(TVSeries)
            .options(
                selectinload(TVSeries.seasons).selectinload(TVSeason.episodes),
                selectinload(TVSeries.releases).selectinload(TVRelease.contributions).selectinload(
                    TVReleaseContribution.person
                ),
                selectinload(TVSeries.releases).selectinload(TVRelease.identifiers),
            )
            .join(TVSeries.releases, isouter=True)
            .join(TVRelease.identifiers, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(TVReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(TVRelease.sku) == normalized,
                )
            )
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _tv_release_seasons(self, series: TVSeries) -> list[SeasonResponse]:
        seasons: list[SeasonResponse] = []
        for season in sorted(series.seasons or [], key=lambda row: (row.season_number, str(row.id))):
            ordered_episodes = sorted(
                season.episodes or [],
                key=lambda episode: (episode.episode_number, episode.original_air_date or date.max, str(episode.id)),
            )
            seasons.append(
                SeasonResponse(
                    season_number=season.season_number,
                    title=season.title or f"Season {season.season_number}",
                    overview=season.overview or series.overview,
                    air_date=season.air_date or next((episode.original_air_date for episode in ordered_episodes if episode.original_air_date), None),
                    episode_count=len(ordered_episodes),
                    poster_url=season.poster_url or series.poster_url,
                    episodes=[
                        EpisodeResponse(
                            episode_number=episode.episode_number,
                            title=episode.title,
                            overview=episode.overview,
                            air_date=episode.original_air_date,
                            runtime_minutes=episode.duration_seconds // 60 if episode.duration_seconds is not None else None,
                            page_count=None,
                        )
                        for episode in ordered_episodes
                    ],
                )
            )
        return seasons

    def _normalized_barcode_expr(self, column):
        return self._normalized_barcode_expr_base(column)

    def _normalized_barcode_expr_base(self, column):
        from sqlalchemy import func

        return func.replace(func.replace(func.replace(column, "-", ""), " ", ""), ".", "")

    def _normalized_barcode(self, value: str) -> str:
        return value.strip().replace("-", "").replace(" ", "").replace(".", "")
