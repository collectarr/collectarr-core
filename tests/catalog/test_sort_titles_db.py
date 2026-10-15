from uuid import uuid4

import pytest

from app.models.base import ItemKind
from app.models.catalog_music_item import MusicItem
from app.services.canonical_correction_targets import CanonicalCorrectionTargetService
from app.services.catalog_music_items import CatalogMusicItemService


@pytest.mark.db
@pytest.mark.asyncio
async def test_music_items_get_automatic_sort_titles(client):
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = CatalogMusicItemService(db)
        automatic = await service.create_from_proposal(_proposal())
        explicit = await service.create_from_proposal(_proposal(sort_title="Pink Floyd Wall"))
        await db.commit()

    assert automatic.sort_title == "Wall, The"
    assert explicit.sort_title == "Pink Floyd Wall"


@pytest.mark.db
@pytest.mark.asyncio
async def test_automatic_sort_title_follows_a_title_correction(client):
    from app.db.session import AsyncSessionLocal

    automatic_id, custom_id = uuid4(), uuid4()
    async with AsyncSessionLocal() as db:
        db.add(MusicItem(id=automatic_id, title="The Wal", sort_title="Wal, The"))
        db.add(MusicItem(id=custom_id, title="The Wal", sort_title="Custom"))
        await db.commit()

    async with AsyncSessionLocal() as db:
        targets = CanonicalCorrectionTargetService(db)
        for entity_id in (automatic_id, custom_id):
            await targets.apply(
                kind=ItemKind.music,
                entity_type="catalog_music_item",
                entity_id=entity_id,
                scope="catalog_item",
                fields={"title": "The Wall"},
            )
        await db.commit()

    async with AsyncSessionLocal() as db:
        assert (await db.get(MusicItem, automatic_id)).sort_title == "Wall, The"
        assert (await db.get(MusicItem, custom_id)).sort_title == "Custom"


def _proposal(**values: object) -> dict[str, object]:
    return {
        "title": "The Wall",
        "artist_credits": [],
        "credits": [],
        "genres": [],
        "extra": [],
        "external_links": [],
        "discs": [],
        **values,
    }
