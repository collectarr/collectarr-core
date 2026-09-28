import pytest

from app.db.session import AsyncSessionLocal
from app.models.canonical_catalog_items import CanonicalCatalogItem
from app.worker.main import (
    catalog_fingerprint,
    index_changed_catalog,
)

async def seed_catalog_item() -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            CanonicalCatalogItem(
                kind="comic",
                title="The Amazing Spider-Man #1",
                identifier_search="|75960604716100111|",
                details={
                    "kind": "comic",
                    "title": "The Amazing Spider-Man #1",
                    "issue_number": "1",
                    "publisher": "Marvel",
                    "barcode": "75960604716100111",
                },
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_catalog_fingerprint_changes_when_catalog_changes():
    async with AsyncSessionLocal() as db:
        initial = await catalog_fingerprint(db)

    await seed_catalog_item()

    async with AsyncSessionLocal() as db:
        updated = await catalog_fingerprint(db)

    assert updated != initial
    assert updated.item_count == 1


@pytest.mark.asyncio
async def test_index_changed_catalog_keeps_last_fingerprint_on_index_failure():
    class FailingSearch:
        async def replace_documents(self, documents):
            raise RuntimeError("index unavailable")

    async with AsyncSessionLocal() as db:
        initial = await catalog_fingerprint(db)

    await seed_catalog_item()

    next_fingerprint = await index_changed_catalog(FailingSearch(), initial)

    assert next_fingerprint == initial
