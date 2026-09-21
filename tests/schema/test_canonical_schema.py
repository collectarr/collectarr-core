import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionLocal


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
            "provider_payload_snapshot_values",
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
            "game_release_identifiers",
            "game_platforms",
            "game_genres",
            "game_release_platforms",
            "game_identifiers",
            "game_company_roles",
            "game_age_ratings",
            "game_series_memberships",
            "boardgame_works",
            "boardgame_editions",
            "boardgame_genres",
            "boardgame_platforms",
            "boardgame_edition_identifiers",
            "boardgame_identifiers",
            "boardgame_contributions",
            "boardgame_mechanics",
            "boardgame_categories",
            "boardgame_families",
            "boardgame_expansions",
            "boardgame_rankings_snapshot",
            "boardgame_player_count_votes",
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
            "admin_audit_log_details",
            "duplicate_review_entities",
            "duplicate_review_details",
            "metadata_proposal_values",
            "person_external_identifiers",
            "music_release_group_genres",
            "music_medium_missing_track_positions",
            "comic_work_missing_issue_numbers",
        }.issubset(tables)
        assert "provider_ingest_jobs" in tables
        assert "metadata_taxonomies" in tables
        provider_ingest_columns = {
            row[0]
            for row in (
                await db.execute(
                    text(
                        """
                        select column_name
                        from information_schema.columns
                        where table_schema = 'public'
                          and table_name = 'provider_ingest_jobs'
                        """
                    )
                )
            ).all()
        }
        assert "resolved_entity_type" in provider_ingest_columns
        assert "resolved_entity_id" in provider_ingest_columns
        assert "item_id" not in provider_ingest_columns

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
        assert json_columns == []

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
