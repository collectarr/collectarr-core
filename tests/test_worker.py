import pytest

from app.db.session import AsyncSessionLocal
from app.worker.main import catalog_fingerprint
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
    assert updated.release_count == 0
