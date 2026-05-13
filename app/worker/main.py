import asyncio
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.canonical import Edition, Item, Release, Variant, Volume
from app.search.client import SearchClient
from app.search.documents import item_search_document
from app.storage.client import ObjectStorage


@dataclass(frozen=True)
class CatalogFingerprint:
    item_count: int
    item_updated_at: datetime | None
    edition_count: int
    edition_updated_at: datetime | None
    variant_count: int
    variant_updated_at: datetime | None
    release_count: int
    release_updated_at: datetime | None


async def catalog_fingerprint(db: AsyncSession) -> CatalogFingerprint:
    item_count, item_updated_at = (
        await db.execute(select(func.count(Item.id), func.max(Item.updated_at)))
    ).one()
    edition_count, edition_updated_at = (
        await db.execute(select(func.count(Edition.id), func.max(Edition.updated_at)))
    ).one()
    variant_count, variant_updated_at = (
        await db.execute(select(func.count(Variant.id), func.max(Variant.updated_at)))
    ).one()
    release_count, release_updated_at = (
        await db.execute(select(func.count(Release.id), func.max(Release.updated_at)))
    ).one()
    return CatalogFingerprint(
        item_count=int(item_count),
        item_updated_at=item_updated_at,
        edition_count=int(edition_count),
        edition_updated_at=edition_updated_at,
        variant_count=int(variant_count),
        variant_updated_at=variant_updated_at,
        release_count=int(release_count),
        release_updated_at=release_updated_at,
    )


async def index_once(search: SearchClient | None = None) -> None:
    search = search or SearchClient()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Item).options(
                selectinload(Item.volume).selectinload(Volume.series),
                selectinload(Item.editions).selectinload(Edition.variants),
                selectinload(Item.editions).selectinload(Edition.releases),
            )
        )
        documents = [item_search_document(item) for item in result.scalars().unique()]
        await search.index_documents(documents)


async def main() -> None:
    settings = get_settings()
    search = SearchClient()
    await search.configure()
    ObjectStorage().ensure_bucket()
    last_fingerprint: CatalogFingerprint | None = None

    while True:
        async with AsyncSessionLocal() as db:
            current_fingerprint = await catalog_fingerprint(db)
        if current_fingerprint != last_fingerprint:
            await index_once(search)
            last_fingerprint = current_fingerprint
        await asyncio.sleep(settings.worker_index_interval_seconds)


if __name__ == "__main__":
    asyncio.run(main())
