import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.canonical import Edition, Item
from app.search.client import SearchClient
from app.storage.client import ObjectStorage


async def index_once() -> None:
    search = SearchClient()
    await search.configure()
    storage = ObjectStorage()
    storage.ensure_bucket()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Item).options(selectinload(Item.editions).selectinload(Edition.variants)))
        documents = []
        for item in result.scalars().unique():
            cover_url = None
            publisher = None
            for edition in item.editions:
                publisher = publisher or edition.publisher
                primary = next((variant for variant in edition.variants if variant.is_primary), None)
                if primary:
                    cover_url = primary.cover_image_url
            documents.append(
                {
                    "id": str(item.id),
                    "kind": item.kind.value,
                    "title": item.title,
                    "item_number": item.item_number,
                    "synopsis": item.synopsis,
                    "cover_image_url": cover_url,
                    "publisher": publisher,
                }
            )
        await search.index_documents(documents)


async def main() -> None:
    while True:
        await index_once()
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())

