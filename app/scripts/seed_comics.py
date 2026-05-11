import asyncio
from datetime import date

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import Edition, ExternalProviderId, Franchise, Item, Series, Variant, Volume


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Item).where(Item.title == "The Amazing Spider-Man"))
        if existing.scalar_one_or_none():
            return

        franchise = Franchise(name="Marvel", description="Marvel comic universe metadata seed.")
        series = Series(kind=ItemKind.comic, title="The Amazing Spider-Man", slug="amazing-spider-man")
        volume = Volume(name="The Amazing Spider-Man (1963)", volume_number=1, start_year=1963)
        item = Item(
            kind=ItemKind.comic,
            title="The Amazing Spider-Man",
            item_number="1",
            sort_key="amazing-spider-man-001",
            synopsis="Peter Parker faces a new chapter as Spider-Man in this seed MVP record.",
        )
        edition = Edition(
            title="Standard Edition",
            format="Single Issue",
            publisher="Marvel",
            language="en",
            release_date=date(1963, 3, 1),
        )
        variant = Variant(name="Cover A", is_primary=True)

        series.franchise = franchise
        volume.series = series
        item.volume = volume
        edition.item = item
        variant.edition = edition

        db.add_all([franchise, series, volume, item, edition, variant])
        await db.flush()
        db.add(
            ExternalProviderId(
                provider=ExternalProvider.comicvine,
                provider_item_id="seed-amazing-spider-man-1",
                entity_type="item",
                entity_id=item.id,
            )
        )
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())

