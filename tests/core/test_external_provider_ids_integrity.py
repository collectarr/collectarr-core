import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal

ENTITY_TABLES = {
    "item": "items",
    "bundle_release": "bundle_releases",
    "comic_series": "comic_series",
    "comic_work": "comic_works",
    "comic_volume": "comic_volumes",
    "comic_issue": "comic_issues",
    "manga_series": "manga_series",
    "manga_work": "manga_works",
    "book_series": "book_series",
    "book_work": "book_works",
    "book_edition": "book_editions",
    "music_release": "music_releases",
    "movie_work": "movie_works",
    "game_work": "game_works",
    "game_release": "game_releases",
    "boardgame_work": "boardgame_works",
    "boardgame_edition": "boardgame_editions",
}


@pytest.mark.asyncio
async def test_external_provider_ids_reference_existing_entities(migrated_database):
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    """
                    select entity_type, entity_id
                    from external_provider_ids
                    order by entity_type, entity_id
                    """
                )
            )
        ).all()

        assert rows, "expected at least one external provider id"
        for entity_type, entity_id in rows:
            table_name = ENTITY_TABLES.get(entity_type)
            assert table_name is not None, f"unexpected entity_type {entity_type!r}"
            exists = await db.execute(
                text(f"select 1 from {table_name} where id = :entity_id limit 1"),
                {"entity_id": entity_id},
            )
            assert exists.first() is not None, (
                f"missing {entity_type} row for external_provider_ids.entity_id={entity_id}"
            )
