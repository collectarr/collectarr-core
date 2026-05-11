from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import ItemKind
from app.models.canonical import Edition, Item, Variant, Volume


class MetadataRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _item_detail_stmt(self) -> Select[tuple[Item]]:
        return select(Item).options(
            selectinload(Item.volume).selectinload(Volume.series),
            selectinload(Item.editions).selectinload(Edition.variants),
            selectinload(Item.editions).selectinload(Edition.releases),
        )

    async def get_item(self, item_id: UUID, kind: ItemKind | None = None) -> Item | None:
        stmt = self._item_detail_stmt().where(Item.id == item_id)
        if kind:
            stmt = stmt.where(Item.kind == kind)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def search_items(self, query: str, kind: ItemKind | None = None, limit: int = 25) -> list[Item]:
        pattern = f"%{query.strip()}%"
        stmt = (
            select(Item)
            .options(selectinload(Item.editions).selectinload(Edition.variants))
            .where(or_(Item.title.ilike(pattern), Item.item_number.ilike(pattern)))
            .order_by(Item.sort_key.nullslast(), Item.title)
            .limit(limit)
        )
        if kind:
            stmt = stmt.where(Item.kind == kind)
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

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
