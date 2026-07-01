from uuid import UUID

from sqlalchemy import Select, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    BookEdition,
    BookIdentifier,
    BookWork,
    CharacterAppearance,
    ComicIdentifier,
    ComicIssue,
    ComicWork,
    Edition,
    EntityOrganization,
    EntityPerson,
    Item,
    ItemKindMetadata,
    ItemKindMetadataTaxonomy,
    MovieRelease,
    MovieWork,
    MovieWorkIdentifier,
    StoryArcItem,
    TVRelease,
    TVReleaseIdentifier,
    Variant,
)
from app.models.base import ItemKind


class MetadataRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _kind_metadata_loader(self):
        return selectinload(Item.kind_metadata).selectinload(ItemKindMetadata.taxonomy_links).selectinload(
            ItemKindMetadataTaxonomy.taxonomy
        )

    def _item_detail_stmt(self) -> Select[tuple[Item]]:
        return select(Item).options(
            selectinload(Item.editions).selectinload(Edition.variants),
            selectinload(Item.alias_entries),
            selectinload(Item.link_entries),
            self._kind_metadata_loader(),
            selectinload(Item.provider_links),
            selectinload(Item.primary_bundle_releases),
            selectinload(Item.organization_links).selectinload(EntityOrganization.organization),
            selectinload(Item.creator_links).selectinload(EntityPerson.person),
            selectinload(Item.character_appearances).selectinload(CharacterAppearance.character),
            selectinload(Item.story_arc_items).selectinload(StoryArcItem.story_arc),
        )

    async def get_item(self, item_id: UUID, kind: ItemKind | None = None) -> Item | None:
        stmt = self._item_detail_stmt().where(Item.id == item_id)
        if kind:
            stmt = stmt.where(Item.kind == kind)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

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
    ) -> list[Item]:
        if kind == ItemKind.book:
            return list(await self._search_book_works(query=query, limit=limit, publisher=publisher, imprint=imprint, subtitle=subtitle, series_group=series_group, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        if kind == ItemKind.comic:
            return list(await self._search_comic_works(query=query, limit=limit, publisher=publisher, imprint=imprint, subtitle=subtitle, series_group=series_group, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        if kind == ItemKind.movie:
            return list(await self._search_movie_works(query=query, limit=limit, publisher=publisher, subtitle=subtitle, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        if kind == ItemKind.tv:
            return list(await self._search_tv_releases(query=query, limit=limit, publisher=publisher, subtitle=subtitle, country=country, language=language, age_rating=age_rating, catalog_number=catalog_number, release_status=release_status, year=year, barcode=barcode))
        return []

    async def find_item_by_barcode(self, barcode: str, kind: ItemKind | None = None) -> Item | None:
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
        if kind == ItemKind.comic:
            stmt = (
                select(ComicWork)
                .join(ComicWork.issues)
                .join(ComicIssue.identifiers)
                .where(self._normalized_barcode_expr(ComicIdentifier.value) == normalized)
                .limit(1)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
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
            return result.scalar_one_or_none()
        if kind == ItemKind.tv:
            stmt = (
                select(TVRelease)
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
    ) -> list[TVRelease]:
        stmt = select(TVRelease).order_by(TVRelease.sort_title.asc().nullslast(), TVRelease.title.asc()).limit(limit)
        stmt = stmt.join(TVRelease.identifiers, isouter=True)
        if query and query.strip():
            pattern = f"%{query.strip()}%"
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
        if country and country.strip():
            stmt = stmt.where(TVRelease.region_code.ilike(f"%{country.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(or_(TVRelease.language_audio.any(language.strip()), TVRelease.language_subtitles.any(language.strip())))
        if age_rating and age_rating.strip():
            stmt = stmt.where(TVRelease.content_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(TVRelease.sku.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(TVRelease.format.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", TVRelease.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode_value(barcode)
            stmt = stmt.join(TVRelease.identifiers, isouter=True)
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
        item = await self.db.get(Item, item_id)
        if item is None:
            raise ValueError("item_id does not exist")
        if edition_id:
            edition = await self.db.get(Edition, edition_id)
            if edition is None or edition.item_id != item_id:
                raise ValueError("edition_id does not belong to item_id")
        if variant_id:
            variant = await self.db.get(Variant, variant_id)
            if variant is None or variant.edition_id != edition_id:
                raise ValueError("variant_id does not belong to edition_id")
