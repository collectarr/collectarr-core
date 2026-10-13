import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.models.base import Base


def test_schema_fixture_runs(schema_database):
    assert schema_database is None


@pytest.mark.asyncio
async def test_canonical_catalog_schema_exists(schema_database):
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
        expected_shared_tables = {
            "bundle_releases",
            "bundle_release_components",
            "metadata_taxonomies",
            "organizations",
            "entity_aliases",
            "entity_links",
            "release_statuses",
            "physical_format_refs",
            "book_series",
            "persons",
            "entity_organizations",
            "entity_persons",
            "story_arcs",
            "story_arc_items",
            "characters",
            "character_appearances",
            "tags",
            "entity_tags",
            "image_assets",
            "admin_audit_logs",
            "admin_audit_log_details",
            "duplicate_reviews",
            "duplicate_review_entities",
            "duplicate_review_details",
            "canonical_correction_proposals",
            "canonical_correction_proposal_values",
        }
        canonical_kind_tables = {
            "anime_items",
            "boardgame_items",
            "book_items",
            "comic_items",
            "game_items",
            "manga_items",
            "movie_items",
            "music_items",
            "tv_items",
        }
        assert (expected_shared_tables | canonical_kind_tables) <= tables
        assert tables == set(Base.metadata.tables)
        assert {
            "game_works",
            "game_releases",
            "boardgame_works",
            "boardgame_editions",
            "comic_works",
            "comic_volumes",
            "comic_issues",
            "comic_variants",
            "manga_works",
            "manga_editions",
            "manga_chapters",
            "manga_series",
            "anime_series",
            "anime_releases",
            "anime_episodes",
            "anime_release_media",
            "anime_release_episode_map",
            "book_item_printings",
            "book_item_credits",
            "book_item_identifiers",
            "comic_item_identifiers",
            "game_item_identifiers",
            "boardgame_item_identifiers",
            "manga_item_identifiers",
            "anime_item_media",
            "anime_item_episodes",
            "anime_item_identifiers",
            "tv_item_seasons",
            "tv_item_episodes",
            "tv_item_media",
            "tv_item_identifiers",
        }.isdisjoint(tables)
        assert "metadata_taxonomies" in tables

        json_columns = (
            await db.execute(
                text(
                    """
                    select table_name, column_name, data_type
                    from information_schema.columns
                    where table_schema = 'public'
                      and data_type in ('json', 'jsonb')
                    """
                )
            )
        ).all()
        json_columns = set(json_columns)
        assert ("book_items", "details", "jsonb") in json_columns
        assert ("music_items", "discs", "jsonb") in json_columns
        assert ("music_items", "credits", "jsonb") in json_columns
        assert ("music_items", "release_date", "jsonb") in json_columns

        enum_values = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select enumlabel
                        from pg_enum
                        join pg_type on pg_type.oid = pg_enum.enumtypid
                        where pg_type.typname = 'item_kind'
                        """
                    )
                )
            ).all()
        }
        assert {
            "comic",
            "manga",
            "anime",
            "movie",
            "tv",
            "game",
            "boardgame",
            "book",
            "music",
            "collection",
        }.issubset(enum_values)
