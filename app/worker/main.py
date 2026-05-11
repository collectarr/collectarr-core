import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.canonical import Edition, Item, Volume
from app.search.client import SearchClient
from app.search.documents import item_search_document
from app.storage.client import ObjectStorage


async def index_once() -> None:
    search = SearchClient()
    await search.configure()
    storage = ObjectStorage()
    storage.ensure_bucket()

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
    while True:
        await index_once()
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
