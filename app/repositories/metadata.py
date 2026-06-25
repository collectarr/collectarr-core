from uuid import UUID

from sqlalchemy import Select, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import ItemKind
from app.models.canonical import (
    BundleRelease,
    BundleReleaseItem,
    CharacterAppearance,
    Edition,
    EntityOrganization,
    EntityPerson,
    Item,
    ItemKindMetadata,
    ItemKindMetadataAnime,
    ItemKindMetadataBoardGame,
    ItemKindMetadataBook,
    ItemKindMetadataCollection,
    ItemKindMetadataComic,
    ItemKindMetadataGame,
    ItemKindMetadataManga,
    ItemKindMetadataMovie,
    ItemKindMetadataMusic,
    ItemKindMetadataTaxonomy,
    ItemKindMetadataTv,
    Series,
    StoryArcItem,
    Variant,
    Volume,
)


class MetadataRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _kind_metadata_loader(self):
        return selectinload(Item.kind_metadata).selectin_polymorphic(
            [
                ItemKindMetadataAnime,
                ItemKindMetadataBoardGame,
                ItemKindMetadataBook,
                ItemKindMetadataCollection,
                ItemKindMetadataComic,
                ItemKindMetadataGame,
                ItemKindMetadataManga,
                ItemKindMetadataMovie,
                ItemKindMetadataMusic,
                ItemKindMetadataTv,
            ]
        )

    def _bundle_release_detail_stmt(self) -> Select[tuple[BundleRelease]]:
        return select(BundleRelease).options(
            selectinload(BundleRelease.series),
            selectinload(BundleRelease.volume),
            selectinload(BundleRelease.primary_item),
            selectinload(BundleRelease.provider_links),
            selectinload(BundleRelease.items)
            .selectinload(BundleReleaseItem.item)
            .selectinload(Item.volume)
            .selectinload(Volume.series),
        )

    def _item_detail_stmt(self) -> Select[tuple[Item]]:
        return select(Item).options(
            selectinload(Item.volume).selectinload(Volume.series),
            selectinload(Item.editions).selectinload(Edition.variants),
            selectinload(Item.alias_entries),
            selectinload(Item.link_entries),
            self._kind_metadata_loader(),
            selectinload(Item.kind_metadata).selectinload(ItemKindMetadata.taxonomy_links).selectinload(
                ItemKindMetadataTaxonomy.taxonomy
            ),
            selectinload(Item.kind_metadata.of_type(ItemKindMetadataMusic)).selectinload(
                ItemKindMetadataMusic.tracks
            ),
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

    async def get_bundle_releases_for_item(self, item_id: UUID) -> list[BundleRelease]:
        stmt = (
            self._bundle_release_detail_stmt()
            .join(BundleRelease.items)
            .where(BundleReleaseItem.item_id == item_id)
            .order_by(BundleRelease.release_date.desc().nullslast(), BundleRelease.title.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    async def get_bundle_release(self, bundle_release_id: UUID) -> BundleRelease | None:
        stmt = self._bundle_release_detail_stmt().where(BundleRelease.id == bundle_release_id)
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
        stmt = (
            select(Item)
            .options(
                selectinload(Item.volume).selectinload(Volume.series),
                selectinload(Item.editions).selectinload(Edition.variants),
                selectinload(Item.alias_entries),
                selectinload(Item.link_entries),
                self._kind_metadata_loader(),
                selectinload(Item.kind_metadata).selectinload(ItemKindMetadata.taxonomy_links).selectinload(
                    ItemKindMetadataTaxonomy.taxonomy
                ),
                selectinload(Item.kind_metadata.of_type(ItemKindMetadataMusic)).selectinload(
                    ItemKindMetadataMusic.tracks
                ),
                selectinload(Item.provider_links),
                selectinload(Item.primary_bundle_releases),
                selectinload(Item.organization_links).selectinload(EntityOrganization.organization),
                selectinload(Item.creator_links).selectinload(EntityPerson.person),
                selectinload(Item.character_appearances).selectinload(CharacterAppearance.character),
                selectinload(Item.story_arc_items).selectinload(StoryArcItem.story_arc),
            )
            .join(Item.volume, isouter=True)
            .join(Volume.series, isouter=True)
            .join(Item.editions, isouter=True)
            .join(Edition.variants, isouter=True)
            .join(BundleRelease, BundleRelease.primary_item_id == Item.id, isouter=True)
            .order_by(Item.sort_key.nullslast(), Item.title)
            .limit(limit)
        )
        normalized_query = query.strip() if query else None
        if normalized_query:
            pattern = f"%{normalized_query}%"
            stmt = stmt.where(
                or_(
                    Item.title.ilike(pattern),
                    Item.item_number.ilike(pattern),
                    Volume.name.ilike(pattern),
                    Series.title.ilike(pattern),
                    Edition.publisher.ilike(pattern),
                    Edition.imprint.ilike(pattern),
                    Edition.subtitle.ilike(pattern),
                    Edition.series_group.ilike(pattern),
                    Edition.age_rating.ilike(pattern),
                    Edition.catalog_number.ilike(pattern),
                    Edition.release_status.ilike(pattern),
                    Edition.language.ilike(pattern),
                    Edition.region.ilike(pattern),
                    Edition.upc.ilike(pattern),
                    Edition.isbn.ilike(pattern),
                    Variant.name.ilike(pattern),
                    Variant.barcode.ilike(pattern),
                    Variant.isbn.ilike(pattern),
                    Variant.platform.ilike(pattern),
                    BundleRelease.title.ilike(pattern),
                    BundleRelease.barcode.ilike(pattern),
                    BundleRelease.sku.ilike(pattern),
                )
            )
        if kind:
            stmt = stmt.where(Item.kind == kind)
        if series:
            pattern = f"%{series.strip()}%"
            stmt = stmt.where(
                or_(
                    Item.title.ilike(pattern),
                    Volume.name.ilike(pattern),
                    Series.title.ilike(pattern),
                )
            )
        if issue_number:
            normalized = issue_number.strip()
            stmt = stmt.where(
                or_(Item.item_number == normalized, Item.item_number.ilike(f"%{normalized}%"))
            )
        if publisher:
            stmt = stmt.where(
                or_(
                    Edition.publisher.ilike(f"%{publisher.strip()}%"),
                    BundleRelease.publisher.ilike(f"%{publisher.strip()}%"),
                )
            )
        if imprint:
            stmt = stmt.where(Edition.imprint.ilike(f"%{imprint.strip()}%"))
        if subtitle:
            stmt = stmt.where(Edition.subtitle.ilike(f"%{subtitle.strip()}%"))
        if series_group:
            stmt = stmt.where(Edition.series_group.ilike(f"%{series_group.strip()}%"))
        if country:
            stmt = stmt.where(Edition.region.ilike(f"%{country.strip()}%"))
        if language:
            stmt = stmt.where(Edition.language.ilike(f"%{language.strip()}%"))
        if age_rating:
            stmt = stmt.where(Edition.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number:
            stmt = stmt.where(Edition.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if release_status:
            stmt = stmt.where(Edition.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(
                or_(
                    Volume.start_year == year,
                    extract("year", Edition.release_date) == year,
                    extract("year", BundleRelease.release_date) == year,
                )
            )
        if barcode:
            normalized = self._normalized_barcode_value(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(Edition.upc) == normalized,
                    self._normalized_barcode_expr(Edition.isbn) == normalized,
                    self._normalized_barcode_expr(Variant.barcode) == normalized,
                    self._normalized_barcode_expr(Variant.isbn) == normalized,
                    self._normalized_barcode_expr(Variant.sku) == normalized,
                    self._normalized_barcode_expr(BundleRelease.barcode) == normalized,
                    self._normalized_barcode_expr(BundleRelease.sku) == normalized,
                )
            )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    async def find_item_by_barcode(self, barcode: str, kind: ItemKind | None = None) -> Item | None:
        normalized = self._normalized_barcode_value(barcode)
        if not normalized:
            return None

        stmt = (
            self._item_detail_stmt()
            .join(Item.editions)
            .join(Edition.variants, isouter=True)
            .join(BundleRelease, BundleRelease.primary_item_id == Item.id, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(Edition.upc) == normalized,
                    self._normalized_barcode_expr(Edition.isbn) == normalized,
                    self._normalized_barcode_expr(Variant.barcode) == normalized,
                    self._normalized_barcode_expr(Variant.isbn) == normalized,
                    self._normalized_barcode_expr(Variant.sku) == normalized,
                    self._normalized_barcode_expr(BundleRelease.barcode) == normalized,
                    self._normalized_barcode_expr(BundleRelease.sku) == normalized,
                )
            )
            .limit(1)
        )
        if kind:
            stmt = stmt.where(Item.kind == kind)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

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
