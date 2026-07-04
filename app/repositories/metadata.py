from typing import Any
from uuid import UUID

from sqlalchemy import extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    BoardGameContribution,
    BoardGameEdition,
    BoardGameIdentifier,
    BoardGameMechanic,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookIdentifier,
    BookSeriesMembership,
    BookWork,
    CharacterAppearance,
    ComicContribution,
    ComicIdentifier,
    ComicIssue,
    ComicWork,
    GameCompanyRole,
    GameIdentifier,
    GamePlatform,
    GameRelease,
    GameReleasePlatform,
    GameWork,
    MovieRelease,
    MovieWork,
    MovieWorkContribution,
    MovieWorkIdentifier,
    StoryArcItem,
    TVEpisode,
    TVRelease,
    TVReleaseContribution,
    TVReleaseIdentifier,
    TVReleaseMedia,
    TVSeason,
    TVSeries,
)
from app.models.base import ItemKind


class MetadataRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_item(self, item_id: UUID, kind: ItemKind | None = None) -> Any | None:
        if kind == ItemKind.book:
            stmt = (
                select(BookWork)
                .where(BookWork.id == item_id)
                .options(
                    selectinload(BookWork.contributions).selectinload(BookContribution.person),
                    selectinload(BookWork.series_memberships).selectinload(BookSeriesMembership.series),
                    selectinload(BookWork.editions).selectinload(BookEdition.contributions).selectinload(
                        BookContribution.person
                    ),
                    selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        if kind == ItemKind.game:
            stmt = (
                select(GameWork)
                .where(GameWork.id == item_id)
                .options(
                    selectinload(GameWork.platform_entries),
                    selectinload(GameWork.identifier_entries),
                    selectinload(GameWork.company_role_entries),
                    selectinload(GameWork.age_rating_entries),
                    selectinload(GameWork.series_memberships),
                    selectinload(GameWork.releases).selectinload(GameRelease.platform_links).selectinload(
                        GameReleasePlatform.platform
                    ),
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        if kind == ItemKind.boardgame:
            stmt = (
                select(BoardGameWork)
                .where(BoardGameWork.id == item_id)
                .options(
                    selectinload(BoardGameWork.identifier_entries),
                    selectinload(BoardGameWork.contribution_entries).selectinload(BoardGameContribution.person),
                    selectinload(BoardGameWork.mechanic_entries),
                    selectinload(BoardGameWork.category_entries),
                    selectinload(BoardGameWork.family_entries),
                    selectinload(BoardGameWork.expansion_entries),
                    selectinload(BoardGameWork.ranking_snapshots),
                    selectinload(BoardGameWork.editions).selectinload(BoardGameEdition.player_count_votes),
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        if kind == ItemKind.comic:
            stmt = (
                select(ComicWork)
                .where(ComicWork.id == item_id)
                .options(
                    selectinload(ComicWork.issues).selectinload(ComicIssue.contributions).selectinload(
                        ComicContribution.person
                    ),
                    selectinload(ComicWork.issues).selectinload(ComicIssue.character_appearances).selectinload(
                        CharacterAppearance.character
                    ),
                    selectinload(ComicWork.issues).selectinload(ComicIssue.story_arc_memberships).selectinload(
                        StoryArcItem.story_arc
                    ),
                    selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        if kind == ItemKind.movie:
            stmt = (
                select(MovieWork)
                .where(MovieWork.id == item_id)
                .options(
                    selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
                    selectinload(MovieWork.releases).selectinload(MovieRelease.media),
                    selectinload(MovieWork.identifiers),
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        if kind == ItemKind.tv:
            stmt = (
                select(TVSeries)
                .where(TVSeries.id == item_id)
                .options(
                    selectinload(TVSeries.seasons).selectinload(TVSeason.episodes),
                    selectinload(TVSeries.releases).selectinload(TVRelease.contributions).selectinload(
                        TVReleaseContribution.person
                    ),
                    selectinload(TVSeries.releases).selectinload(TVRelease.identifiers),
                    selectinload(TVSeries.releases).selectinload(TVRelease.media).selectinload(TVReleaseMedia.episodes),
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        return None

    async def search_items(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        limit: int = 25,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        imprint: str | None = None,
        subtitle: str | None = None,
        series_group: str | None = None,
        country: str | None = None,
        language: str | None = None,
        age_rating: str | None = None,
        catalog_number: str | None = None,
        release_status: str | None = None,
        year: int | None = None,
        barcode: str | None = None,
    ) -> list[Any]:
        if kind == ItemKind.book:
            return list(await self._search_book_works(query=query, limit=limit, publisher=publisher, imprint=imprint, subtitle=subtitle, series_group=series_group, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        if kind == ItemKind.game:
            return list(await self._search_game_works(query=query, limit=limit, publisher=publisher, subtitle=subtitle, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        if kind == ItemKind.boardgame:
            return list(await self._search_boardgame_works(query=query, limit=limit, publisher=publisher, subtitle=subtitle, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        if kind == ItemKind.comic:
            return list(await self._search_comic_works(query=query, limit=limit, publisher=publisher, imprint=imprint, subtitle=subtitle, series_group=series_group, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        if kind == ItemKind.movie:
            return list(await self._search_movie_works(query=query, limit=limit, publisher=publisher, subtitle=subtitle, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        if kind == ItemKind.tv:
            return list(await self._search_tv_releases(query=query, limit=limit, publisher=publisher, subtitle=subtitle, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        return []

    async def find_item_by_barcode(self, barcode: str, kind: ItemKind | None = None) -> Any | None:
        normalized = self._normalized_barcode_value(barcode)
        if not normalized:
            return None
        if kind == ItemKind.book:
            stmt = (
                select(BookWork)
                .join(BookWork.editions)
                .join(BookEdition.identifiers)
                .where(
                    or_(
                        self._normalized_barcode_expr(BookIdentifier.value) == normalized,
                        self._normalized_barcode_expr(BookIdentifier.normalized_value) == normalized,
                    )
                )
                .limit(1)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        if kind == ItemKind.game:
            stmt = (
                select(GameWork)
                .join(GameWork.releases)
                .where(
                    or_(
                        self._normalized_barcode_expr(GameRelease.barcode) == normalized,
                        self._normalized_barcode_expr(GameRelease.catalog_number) == normalized,
                    )
                )
                .limit(1)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        if kind == ItemKind.boardgame:
            stmt = (
                select(BoardGameWork)
                .join(BoardGameWork.editions)
                .where(self._normalized_barcode_expr(BoardGameEdition.barcode) == normalized)
                .limit(1)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        if kind == ItemKind.comic:
            stmt = (
                select(ComicWork)
                .join(ComicWork.issues)
                .join(ComicIssue.identifiers)
                .where(self._normalized_barcode_expr(ComicIdentifier.value) == normalized)
                .limit(1)
            )
            result = await self.db.execute(stmt)
            match = result.scalar_one_or_none()
            if match is not None:
                return match
            return None
        if kind == ItemKind.movie:
            stmt = (
                select(MovieWork)
                .join(MovieWork.releases)
                .join(MovieWork.identifiers, isouter=True)
                .where(
                    or_(
                        self._normalized_barcode_expr(MovieWorkIdentifier.value) == normalized,
                        self._normalized_barcode_expr(MovieRelease.barcode) == normalized,
                        self._normalized_barcode_expr(MovieRelease.sku) == normalized,
                    )
                )
                .limit(1)
            )
            result = await self.db.execute(stmt)
            match = result.scalar_one_or_none()
            if match is not None:
                return match
            return None
        if kind == ItemKind.tv:
            stmt = (
                select(TVSeries)
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
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        return None

    async def _search_book_works(
        self,
        *,
        query: str | None,
        limit: int,
        publisher: str | None,
        imprint: str | None,
        subtitle: str | None,
        series_group: str | None,
        country: str | None,
        language: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
    ) -> list[BookWork]:
        stmt = select(BookWork).order_by(BookWork.sort_title.asc().nullslast(), BookWork.title.asc()).limit(limit)
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(BookWork.editions, isouter=True).where(
                or_(
                    BookWork.title.ilike(pattern),
                    BookWork.subtitle.ilike(pattern),
                    BookEdition.display_title.ilike(pattern),
                    BookEdition.edition_statement.ilike(pattern),
                    BookEdition.publisher.ilike(pattern),
                    BookEdition.imprint.ilike(pattern),
                )
            )
        else:
            stmt = stmt.join(BookWork.editions, isouter=True)
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
            stmt = stmt.where(BookEdition.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(BookEdition.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", BookEdition.publication_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode_value(barcode)
            stmt = stmt.join(BookEdition.identifiers, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(BookIdentifier.value) == normalized,
                    self._normalized_barcode_expr(BookIdentifier.normalized_value) == normalized,
                )
            )
        if series_group and series_group.strip():
            stmt = stmt.where(BookWork.title.ilike(f"%{series_group.strip()}%"))
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    async def _search_game_works(
        self,
        *,
        query: str | None,
        limit: int,
        publisher: str | None,
        subtitle: str | None,
        country: str | None,
        language: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
    ) -> list[GameWork]:
        stmt = (
            select(GameWork)
            .options(
                selectinload(GameWork.platform_entries),
                selectinload(GameWork.identifier_entries),
                selectinload(GameWork.company_role_entries),
                selectinload(GameWork.age_rating_entries),
                selectinload(GameWork.series_memberships),
                selectinload(GameWork.releases).selectinload(GameRelease.platform_links).selectinload(
                    GameReleasePlatform.platform
                ),
            )
            .order_by(GameWork.sort_title.asc().nullslast(), GameWork.title.asc())
            .limit(limit)
        )
        stmt = (
            stmt.join(GameWork.releases, isouter=True)
            .join(GameWork.platform_entries, isouter=True)
            .join(GameWork.identifier_entries, isouter=True)
            .join(GameWork.company_role_entries, isouter=True)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    GameWork.title.ilike(pattern),
                    GameWork.subtitle.ilike(pattern),
                    GameRelease.release_title.ilike(pattern),
                    GameRelease.publisher.ilike(pattern),
                    GameRelease.platform.ilike(pattern),
                    GamePlatform.platform_name.ilike(pattern),
                    GameIdentifier.value.ilike(pattern),
                    GameCompanyRole.role.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(GameRelease.publisher.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(GameWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(GameRelease.region_code.ilike(f"%{country.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(GameRelease.language.ilike(f"%{language.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(GameWork.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(GameRelease.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(GameRelease.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", GameRelease.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode_value(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(GameIdentifier.value) == normalized,
                    self._normalized_barcode_expr(GameIdentifier.normalized_value) == normalized,
                    self._normalized_barcode_expr(GameRelease.barcode) == normalized,
                    self._normalized_barcode_expr(GameRelease.catalog_number) == normalized,
                )
            )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    async def _search_boardgame_works(
        self,
        *,
        query: str | None,
        limit: int,
        publisher: str | None,
        subtitle: str | None,
        country: str | None,
        language: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
    ) -> list[BoardGameWork]:
        stmt = (
            select(BoardGameWork)
            .options(
                selectinload(BoardGameWork.identifier_entries),
                selectinload(BoardGameWork.contribution_entries).selectinload(BoardGameContribution.person),
                selectinload(BoardGameWork.mechanic_entries),
                selectinload(BoardGameWork.category_entries),
                selectinload(BoardGameWork.family_entries),
                selectinload(BoardGameWork.expansion_entries),
                selectinload(BoardGameWork.ranking_snapshots),
                selectinload(BoardGameWork.editions).selectinload(BoardGameEdition.player_count_votes),
            )
            .order_by(BoardGameWork.sort_title.asc().nullslast(), BoardGameWork.title.asc())
            .limit(limit)
        )
        stmt = (
            stmt.join(BoardGameWork.editions, isouter=True)
            .join(BoardGameWork.identifier_entries, isouter=True)
            .join(BoardGameWork.contribution_entries, isouter=True)
            .join(BoardGameWork.mechanic_entries, isouter=True)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    BoardGameWork.title.ilike(pattern),
                    BoardGameWork.subtitle.ilike(pattern),
                    BoardGameEdition.edition_title.ilike(pattern),
                    BoardGameEdition.publisher.ilike(pattern),
                    BoardGameEdition.format.ilike(pattern),
                    BoardGameIdentifier.value.ilike(pattern),
                    BoardGameContribution.role.ilike(pattern),
                    BoardGameMechanic.value.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(BoardGameEdition.publisher.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(BoardGameWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(BoardGameEdition.country.ilike(f"%{country.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(BoardGameEdition.language.ilike(f"%{language.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(BoardGameWork.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(BoardGameEdition.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(BoardGameEdition.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", BoardGameEdition.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode_value(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(BoardGameIdentifier.value) == normalized,
                    self._normalized_barcode_expr(BoardGameIdentifier.normalized_value) == normalized,
                    self._normalized_barcode_expr(BoardGameEdition.barcode) == normalized,
                )
            )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    async def _search_comic_works(
        self,
        *,
        query: str | None,
        limit: int,
        publisher: str | None,
        imprint: str | None,
        subtitle: str | None,
        series_group: str | None,
        country: str | None,
        language: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
    ) -> list[ComicWork]:
        stmt = select(ComicWork).order_by(ComicWork.sort_title.asc().nullslast(), ComicWork.title.asc()).limit(limit)
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(ComicWork.issues, isouter=True).where(
                or_(
                    ComicWork.title.ilike(pattern),
                    ComicIssue.issue_number.ilike(pattern),
                    ComicIssue.display_title.ilike(pattern),
                    ComicIssue.publisher.ilike(pattern),
                    ComicIssue.imprint.ilike(pattern),
                )
            )
        else:
            stmt = stmt.join(ComicWork.issues, isouter=True)
        if publisher and publisher.strip():
            stmt = stmt.where(ComicIssue.publisher.ilike(f"%{publisher.strip()}%"))
        if imprint and imprint.strip():
            stmt = stmt.where(ComicIssue.imprint.ilike(f"%{imprint.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(ComicIssue.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(ComicIssue.region.ilike(f"%{country.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(ComicIssue.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", ComicIssue.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode_value(barcode)
            stmt = stmt.join(ComicIssue.identifiers, isouter=True).where(
                self._normalized_barcode_expr(ComicIdentifier.value) == normalized
            )
        if subtitle and subtitle.strip():
            stmt = stmt.where(ComicWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if series_group and series_group.strip():
            stmt = stmt.where(ComicWork.title.ilike(f"%{series_group.strip()}%"))
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    async def _search_movie_works(
        self,
        *,
        query: str | None,
        limit: int,
        publisher: str | None,
        subtitle: str | None,
        country: str | None,
        language: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
    ) -> list[MovieWork]:
        stmt = select(MovieWork).order_by(MovieWork.sort_title.asc().nullslast(), MovieWork.title.asc()).limit(limit)
        stmt = stmt.join(MovieWork.releases, isouter=True)
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    MovieWork.title.ilike(pattern),
                    MovieWork.subtitle.ilike(pattern),
                    MovieRelease.publisher.ilike(pattern),
                    MovieRelease.distributor.ilike(pattern),
                    MovieRelease.format.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(or_(MovieRelease.publisher.ilike(f"%{publisher.strip()}%"), MovieRelease.distributor.ilike(f"%{publisher.strip()}%")))
        if subtitle and subtitle.strip():
            stmt = stmt.where(MovieWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(MovieRelease.region_code.ilike(f"%{country.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(or_(MovieRelease.language_audio.any(language.strip()), MovieRelease.language_subtitles.any(language.strip())))
        if age_rating and age_rating.strip():
            stmt = stmt.where(MovieWork.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(or_(MovieRelease.sku.ilike(f"%{catalog_number.strip()}%"), MovieRelease.barcode.ilike(f"%{catalog_number.strip()}%")))
        if release_status and release_status.strip():
            stmt = stmt.where(MovieRelease.release_type.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", MovieRelease.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode_value(barcode)
            stmt = stmt.join(MovieWork.identifiers, isouter=True)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(MovieWorkIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MovieRelease.barcode) == normalized,
                    self._normalized_barcode_expr(MovieRelease.sku) == normalized,
                )
            )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    async def _search_tv_releases(
        self,
        *,
        query: str | None,
        limit: int,
        publisher: str | None,
        subtitle: str | None,
        country: str | None,
        language: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
    ) -> list[TVSeries]:
        stmt = (
            select(TVSeries)
            .options(
                selectinload(TVSeries.seasons).selectinload(TVSeason.episodes),
                selectinload(TVSeries.releases).selectinload(TVRelease.contributions).selectinload(
                    TVReleaseContribution.person
                ),
                selectinload(TVSeries.releases).selectinload(TVRelease.identifiers),
                selectinload(TVSeries.releases).selectinload(TVRelease.media).selectinload(TVReleaseMedia.episodes),
            )
            .order_by(TVSeries.sort_title.asc().nullslast(), TVSeries.title.asc())
            .limit(limit)
        )
        stmt = stmt.join(TVSeries.releases, isouter=True).join(TVRelease.identifiers, isouter=True)
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    TVSeries.title.ilike(pattern),
                    TVSeries.overview.ilike(pattern),
                    TVSeries.network.ilike(pattern),
                    TVRelease.sku.ilike(pattern),
                    TVSeries.status.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(TVSeries.network.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(TVSeries.overview.ilike(f"%{subtitle.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(TVSeries.country.ilike(f"%{country.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(TVSeries.original_language.ilike(f"%{language.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(TVSeries.status.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(TVRelease.sku.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(TVSeries.status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", TVSeries.first_air_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode_value(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(TVReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(TVRelease.sku) == normalized,
                )
            )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    def _normalized_barcode_expr(self, column):
        return func.replace(func.replace(func.replace(column, "-", ""), " ", ""), ".", "")

    def _normalized_barcode_value(self, value: str) -> str:
        return value.strip().replace("-", "").replace(" ", "").replace(".", "")

    async def validate_refs(
        self, item_id: UUID, edition_id: UUID | None, variant_id: UUID | None
    ) -> None:
        del item_id, edition_id, variant_id
