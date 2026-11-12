from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.catalog_game_item import GameItem
from app.services.catalog_game_items import CatalogGameItemService

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_editions_share_a_game_id_but_have_their_own_media_ids(client):
    async with AsyncSessionLocal() as db:
        service = CatalogGameItemService(db)
        game = await service.create_from_proposal({"title": "Identity fixture", "platforms": ["PS5"]})
        editions = [await service.create_from_proposal({
            "title": "Identity fixture", "game_id": str(game.game_id),
            "platforms": ["PS5"], "barcode": barcode, "release_region": region,
        }) for barcode, region in [("123456", "EU"), ("987654", "US")]]
        await db.commit()
    assert game.media_id is None
    assert {item.game_id for item in editions} == {game.id}
    assert {item.media_id for item in editions} == {item.id for item in editions}
    assert len({item.media_id for item in editions}) == 2
    for item in [game, *editions]:
        result = await client.get(f"/api/v1/metadata/games/items/{item.id}")
        assert result.status_code == 200, result.text
        assert result.json()["game_id"] == str(game.id)
        assert result.json()["media_id"] == (str(item.id) if item != game else None)
    search = await client.get("/api/v1/search", params={"kind": "game", "q": "Identity fixture"})
    assert search.status_code == 200, search.text
    by_id = {row["id"]: row["kind_data"] for row in search.json()["items"]}
    assert by_id[str(game.id)]["game_id"] == str(game.id)
    for item in editions:
        assert by_id[str(item.id)]["game_id"] == str(game.id)
        assert by_id[str(item.id)]["media_id"] == str(item.id)


async def test_an_unlinked_edition_gets_a_new_game_without_merging_similar_titles(client):
    async with AsyncSessionLocal() as db:
        service = CatalogGameItemService(db)
        first = await service.create_from_proposal({"title": "Same title", "barcode": "111"})
        second = await service.create_from_proposal({"title": "Same title", "barcode": "222"})
        assert first.media_id == first.id
        assert first.game_id != first.id
        assert second.game_id != first.game_id
        parent = await service.get(first.game_id)
        assert parent.media_id is None
        assert parent.barcode is None
        await db.commit()


async def test_editions_cannot_link_to_another_edition_or_a_different_platform(client):
    async with AsyncSessionLocal() as db:
        service = CatalogGameItemService(db)
        edition = await service.create_from_proposal({"title": "Parent fixture", "barcode": "123", "platforms": ["PS5"]})
        count = await db.scalar(select(func.count()).select_from(GameItem))
        for parent_id, platform in [(edition.id, "PS5"), (uuid4(), "PS5"), (edition.game_id, "PC")]:
            with pytest.raises(ValueError):
                await service.create_from_proposal({"title": "Invalid", "game_id": str(parent_id), "platforms": [platform]})
        assert await db.scalar(select(func.count()).select_from(GameItem)) == count
