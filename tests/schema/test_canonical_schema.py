import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_database_schema_contains_only_active_catalog_item_tables(schema_database):
    async with AsyncSessionLocal() as db:
        tables = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select table_name
                        from information_schema.tables
                        where table_schema = 'public'
                        """
                    )
                )
            ).all()
        }

    expected = {
        "users",
        "catalog_items",
        "catalog_item_identities",
        "image_assets",
        "image_cache_entries",
        "admin_audit_logs",
        "admin_audit_log_details",
        "duplicate_reviews",
        "duplicate_review_entities",
        "duplicate_review_details",
    }
    legacy = {
        "book_works",
        "book_editions",
        "comic_works",
        "comic_issues",
        "game_works",
        "game_releases",
        "music_release_groups",
        "music_releases",
        "movie_works",
        "movie_releases",
        "tv_series",
        "tv_releases",
        "provider_ingest_jobs",
        "provider_payload_snapshots",
    }

    assert expected <= tables
    assert not legacy & tables
