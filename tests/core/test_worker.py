import pytest

from app.db.session import AsyncSessionLocal
from app.worker.main import (
    catalog_fingerprint,
    index_changed_catalog,
)
from tests.helpers import seed_comic


@pytest.mark.asyncio
async def test_catalog_fingerprint_changes_when_catalog_changes():
    async with AsyncSessionLocal() as db:
        initial = await catalog_fingerprint(db)

    await seed_comic()

    async with AsyncSessionLocal() as db:
        updated = await catalog_fingerprint(db)

    assert updated != initial
    assert updated.item_count == 1
    assert updated.edition_count == 1
    assert updated.variant_count == 1


@pytest.mark.asyncio
async def test_index_changed_catalog_keeps_last_fingerprint_on_index_failure():
    class FailingSearch:
        async def index_documents(self, documents):
            raise RuntimeError("index unavailable")

    async with AsyncSessionLocal() as db:
        initial = await catalog_fingerprint(db)

    await seed_comic()

    next_fingerprint = await index_changed_catalog(FailingSearch(), initial)

    assert next_fingerprint == initial
