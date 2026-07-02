import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal


def test_schema_bootstrap_fixture_runs(migrated_database):
    assert migrated_database is None


@pytest.mark.asyncio
async def test_generalized_catalog_schema_exists(migrated_database):
    async with AsyncSessionLocal() as db:
        deprecated_table = "item" + "_kind_metadata"
        deprecated_taxonomy_table = "item" + "_kind_metadata_taxonomies"
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
        assert {
            "bundle_releases",
            "bundle_release_components",
            "metadata_taxonomies",
            "organizations",
            "entity_aliases",
            "entity_links",
            "release_statuses",
            "physical_format_refs",
            "provider_payload_snapshots",
            "book_works",
            "book_series",
            "book_editions",
            "book_printings",
            "book_contributions",
            "book_identifiers",
            "book_series_memberships",
            "comic_series",
            "game_works",
            "game_releases",
            "boardgame_works",
            "boardgame_editions",
            "comic_works",
            "comic_volumes",
            "comic_issues",
            "comic_contributions",
            "comic_identifiers",
            "comic_story_arc_memberships",
            "comic_character_appearances",
            "comic_series_memberships",
            "comic_series_relations",
            "manga_series",
            "manga_series_relations",
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
            "image_cache_entries",
            "admin_audit_logs",
        }.issubset(tables)
        assert "bundle_release_items" not in tables
        assert f"{deprecated_table}_anime" not in tables
        assert f"{deprecated_table}_boardgame" not in tables
        assert f"{deprecated_table}_book" not in tables
        assert f"{deprecated_table}_collection" not in tables
        assert f"{deprecated_table}_comic" not in tables
        assert f"{deprecated_table}_game" not in tables
        assert f"{deprecated_table}_manga" not in tables
        assert f"{deprecated_table}_movie" not in tables
        assert f"{deprecated_table}_music" not in tables
        assert f"{deprecated_table}_tv" not in tables
        assert f"{deprecated_table}_music_tracks" not in tables
        assert "metadata_taxonomies" in tables
        assert deprecated_taxonomy_table in tables
        assert "tracking_entries" not in tables
        assert "releases" not in tables

        deprecated_kind_columns = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select column_name
                        from information_schema.columns
                        where table_schema = 'public'
                          and table_name = 'item' || '_kind_metadata'
                        """
                    )
                )
            ).all()
        }
        assert "metadata_json" in deprecated_kind_columns

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

        provider_values = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select enumlabel
                        from pg_enum
                        join pg_type on pg_type.oid = pg_enum.enumtypid
                        where pg_type.typname = 'external_provider'
                        """
                    )
                )
            ).all()
        }
        assert "gcd" in provider_values
