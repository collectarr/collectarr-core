from __future__ import annotations

from collections import defaultdict
from datetime import date

from fastapi import status
from sqlalchemy import extract, or_, select
from sqlalchemy.orm import selectinload

from app.core.errors import ApiHTTPException
from app.models import TVEpisode, TVRelease, TVReleaseContribution, TVReleaseIdentifier
from app.models.base import ExternalProvider, ItemKind
from app.providers.base import NormalizedSeason
from app.schemas import EpisodeResponse as ProviderEpisodeResponse
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
            select(TVRelease)
            .options(
                selectinload(TVRelease.contributions).selectinload(TVReleaseContribution.person),
                selectinload(TVRelease.media),
                selectinload(TVRelease.identifiers),
            )
            .order_by(TVRelease.sort_title.asc().nullslast(), TVRelease.title.asc())
            .limit(limit)
        )
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        if pattern:
            stmt = stmt.where(
                or_(
                    TVRelease.title.ilike(pattern),
                    TVRelease.description.ilike(pattern),
                    TVRelease.publisher.ilike(pattern),
                    TVRelease.sku.ilike(pattern),
                    TVRelease.content_rating.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(TVRelease.publisher.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(TVRelease.description.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(
                or_(
                    TVRelease.language_audio.any(language.strip()),
                    TVRelease.language_subtitles.any(language.strip()),
                )
            )
        if country and country.strip():
            stmt = stmt.where(TVRelease.region_code.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(TVRelease.content_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(TVRelease.sku.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(TVRelease.format.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", TVRelease.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(TVReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(TVRelease.sku) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt.join(TVRelease.identifiers, isouter=True))).scalars().unique())
        return [self._tv_search_result(release) for release in rows]

    def _tv_search_result(self, release: TVRelease) -> SearchResult:
        return SearchResult(
            id=release.id,
            kind=ItemKind.tv,
            title=release.title,
            synopsis=release.description,
            cover_image_url=release.cover_image_url,
            physical_format=release.format,
            publisher=release.publisher,
            release_date=release.release_date,
            release_year=release.release_date.year if release.release_date else None,
            barcode=next((identifier.value for identifier in release.identifiers or [] if identifier.value), release.sku),
            catalog_number=release.sku,
            country=release.region_code,
            age_rating=release.content_rating,
            language=(release.language_audio or [None])[0],
            release_status=release.format,
        )

    async def _tv_release_by_barcode(self, barcode: str) -> TVRelease | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(TVRelease)
            .options(
                selectinload(TVRelease.contributions).selectinload(TVReleaseContribution.person),
                selectinload(TVRelease.media),
                selectinload(TVRelease.identifiers),
            )
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

    async def get_provider_seasons(self, provider_name, provider_item_id: str) -> list[SeasonResponse]:
        provider = self.providers.maybe_get(provider_name)
        if provider is None:
            raise ApiHTTPException(status_code=status.HTTP_400_BAD_REQUEST, code="provider_not_configured", detail=f"Provider '{provider_name.value}' is not configured")
        if not hasattr(provider, "get_seasons"):
            raise ApiHTTPException(status_code=status.HTTP_400_BAD_REQUEST, code="provider_seasons_unsupported", detail=f"Provider '{provider_name.value}' does not support seasons")
        seasons: list[NormalizedSeason] = await provider.get_seasons(provider_item_id)
        return [SeasonResponse(season_number=s.season_number, title=s.title, provider_item_id=s.provider_item_id, overview=s.overview, air_date=s.air_date, episode_count=s.episode_count, poster_url=s.poster_url, episodes=[ProviderEpisodeResponse(episode_number=ep.episode_number, title=ep.title, provider_item_id=ep.provider_item_id, overview=ep.overview, air_date=ep.air_date, runtime_minutes=ep.runtime_minutes, page_count=ep.page_count) for ep in s.episodes]) for s in seasons]

    async def get_provider_volumes(self, provider_name, provider_item_id: str) -> list[SeasonResponse]:
        provider = self.providers.maybe_get(provider_name)
        if provider is None:
            raise ApiHTTPException(status_code=status.HTTP_400_BAD_REQUEST, code="provider_not_configured", detail=f"Provider '{provider_name.value}' is not configured")
        if not hasattr(provider, "get_volumes"):
            raise ApiHTTPException(status_code=status.HTTP_400_BAD_REQUEST, code="provider_volumes_unsupported", detail=f"Provider '{provider_name.value}' does not support volumes")
        volumes: list[NormalizedSeason] = await provider.get_volumes(provider_item_id)
        return [SeasonResponse(season_number=v.season_number, title=v.title, provider_item_id=v.provider_item_id, overview=v.overview, air_date=v.air_date, episode_count=v.episode_count, poster_url=v.poster_url, episodes=[ProviderEpisodeResponse(episode_number=ep.episode_number, title=ep.title, provider_item_id=ep.provider_item_id, overview=ep.overview, air_date=ep.air_date, runtime_minutes=ep.runtime_minutes, page_count=ep.page_count) for ep in v.episodes]) for v in volumes]

    async def _tv_release_seasons(self, release: TVRelease) -> list[SeasonResponse]:
        episodes_by_season: dict[int, list[TVEpisode]] = defaultdict(list)
        for episode in release.episodes or []:
            episodes_by_season[episode.season_number].append(episode)
        season_provider_item_id = release.metadata_json.get("provider_item_id") if isinstance(release.metadata_json, dict) else None
        if not season_provider_item_id:
            season_provider_item_id = next((link.provider_item_id for link in await self._provider_links_for_entity("tv_release", release.id) if link.provider == ExternalProvider.tmdb and link.provider_item_id), None)
        seasons: list[SeasonResponse] = []
        for season_number, episodes in sorted(episodes_by_season.items(), key=lambda item: item[0]):
            ordered_episodes = sorted(episodes, key=lambda episode: (episode.episode_number, episode.original_air_date or date.max, str(episode.id)))
            seasons.append(SeasonResponse(season_number=season_number, title=f"Season {season_number}", provider_item_id=season_provider_item_id, overview=release.description, air_date=next((episode.original_air_date for episode in ordered_episodes if episode.original_air_date), None), episode_count=len(ordered_episodes), poster_url=release.cover_image_url, episodes=[ProviderEpisodeResponse(episode_number=episode.episode_number, title=episode.title, provider_item_id=(episode.metadata_json.get("provider_item_id") if isinstance(episode.metadata_json, dict) else None), overview=episode.overview, air_date=episode.original_air_date, runtime_minutes=episode.duration_seconds // 60 if episode.duration_seconds is not None else None, page_count=None) for episode in ordered_episodes]))
        return seasons
