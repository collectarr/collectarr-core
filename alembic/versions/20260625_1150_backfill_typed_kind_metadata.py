"""Backfill typed item_kind_metadata rows from legacy normalized JSON.

Revision ID: 20260625_1150
Revises: 20260625_1100
Create Date: 2026-06-25 11:50:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_1150"
down_revision: str | None = "20260625_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        WITH first_edition AS (
            SELECT DISTINCT ON (e.item_id)
                e.item_id,
                CASE
                    WHEN jsonb_typeof(e.metadata_json->'normalized') = 'object'
                    THEN e.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM editions AS e
            ORDER BY e.item_id, e.release_date DESC NULLS LAST, e.created_at ASC, e.id ASC
        ),
        source AS (
            SELECT
                i.id AS item_id,
                i.kind,
                (
                    COALESCE(fe.normalized, '{}'::jsonb)
                    || CASE
                        WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                        THEN i.metadata_json->'normalized'
                        ELSE '{}'::jsonb
                    END
                ) AS normalized
            FROM items AS i
            LEFT JOIN first_edition AS fe ON fe.item_id = i.id
        ),
        candidates AS (
            SELECT *
            FROM source
            WHERE (
                NULLIF(BTRIM(normalized->>'audience_rating'), '') IS NOT NULL OR
                jsonb_typeof(normalized->'genres') = 'array' OR
                jsonb_typeof(normalized->'platforms') = 'array' OR
                jsonb_typeof(normalized->'tracks') = 'array' OR
                (normalized->>'track_count') ~ '^[0-9]+$' OR
                NULLIF(BTRIM(normalized->>'color'), '') IS NOT NULL
            )
        )
        INSERT INTO item_kind_metadata (id, item_id, kind, audience_rating, created_at, updated_at)
        SELECT
            c.item_id,
            c.item_id,
            c.kind,
            NULLIF(BTRIM(c.normalized->>'audience_rating'), ''),
            now(),
            now()
        FROM candidates AS c
        ON CONFLICT (item_id)
        DO UPDATE SET
            audience_rating = COALESCE(EXCLUDED.audience_rating, item_kind_metadata.audience_rating),
            updated_at = now()
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_comic (id, genres)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END
        FROM source AS s
        WHERE s.kind = 'comic'
        ON CONFLICT (id)
        DO UPDATE SET genres = COALESCE(EXCLUDED.genres, item_kind_metadata_comic.genres)
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_manga (id, genres)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END
        FROM source AS s
        WHERE s.kind = 'manga'
        ON CONFLICT (id)
        DO UPDATE SET genres = COALESCE(EXCLUDED.genres, item_kind_metadata_manga.genres)
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_book (id, genres)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END
        FROM source AS s
        WHERE s.kind = 'book'
        ON CONFLICT (id)
        DO UPDATE SET genres = COALESCE(EXCLUDED.genres, item_kind_metadata_book.genres)
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_collection (id, genres)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END
        FROM source AS s
        WHERE s.kind = 'collection'
        ON CONFLICT (id)
        DO UPDATE SET genres = COALESCE(EXCLUDED.genres, item_kind_metadata_collection.genres)
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_boardgame (id, genres, platforms)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END,
            CASE
                WHEN jsonb_typeof(s.normalized->'platforms') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'platforms'))
                ELSE NULL
            END
        FROM source AS s
        WHERE s.kind = 'boardgame'
        ON CONFLICT (id)
        DO UPDATE SET
            genres = COALESCE(EXCLUDED.genres, item_kind_metadata_boardgame.genres),
            platforms = COALESCE(EXCLUDED.platforms, item_kind_metadata_boardgame.platforms)
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_game (id, genres, platforms)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END,
            CASE
                WHEN jsonb_typeof(s.normalized->'platforms') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'platforms'))
                ELSE NULL
            END
        FROM source AS s
        WHERE s.kind = 'game'
        ON CONFLICT (id)
        DO UPDATE SET
            genres = COALESCE(EXCLUDED.genres, item_kind_metadata_game.genres),
            platforms = COALESCE(EXCLUDED.platforms, item_kind_metadata_game.platforms)
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_music (id, genres, track_count, tracks)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END,
            CASE
                WHEN (s.normalized->>'track_count') ~ '^[0-9]+$'
                THEN (s.normalized->>'track_count')::int
                WHEN jsonb_typeof(s.normalized->'tracks') = 'array'
                THEN jsonb_array_length(s.normalized->'tracks')
                ELSE NULL
            END,
            CASE
                WHEN jsonb_typeof(s.normalized->'tracks') = 'array'
                THEN s.normalized->'tracks'
                ELSE NULL
            END
        FROM source AS s
        WHERE s.kind = 'music'
        ON CONFLICT (id)
        DO UPDATE SET
            genres = COALESCE(EXCLUDED.genres, item_kind_metadata_music.genres),
            track_count = COALESCE(EXCLUDED.track_count, item_kind_metadata_music.track_count),
            tracks = COALESCE(EXCLUDED.tracks, item_kind_metadata_music.tracks)
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_anime (id, genres, color)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END,
            NULLIF(BTRIM(s.normalized->>'color'), '')
        FROM source AS s
        WHERE s.kind = 'anime'
        ON CONFLICT (id)
        DO UPDATE SET
            genres = COALESCE(EXCLUDED.genres, item_kind_metadata_anime.genres),
            color = COALESCE(EXCLUDED.color, item_kind_metadata_anime.color)
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_movie (id, genres, color)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END,
            NULLIF(BTRIM(s.normalized->>'color'), '')
        FROM source AS s
        WHERE s.kind = 'movie'
        ON CONFLICT (id)
        DO UPDATE SET
            genres = COALESCE(EXCLUDED.genres, item_kind_metadata_movie.genres),
            color = COALESCE(EXCLUDED.color, item_kind_metadata_movie.color)
        """
    )
    op.execute(
        """
        WITH source AS (
            SELECT
                ikm.id AS metadata_id,
                ikm.kind,
                CASE
                    WHEN jsonb_typeof(i.metadata_json->'normalized') = 'object'
                    THEN i.metadata_json->'normalized'
                    ELSE '{}'::jsonb
                END AS normalized
            FROM item_kind_metadata AS ikm
            JOIN items AS i ON i.id = ikm.item_id
        )
        INSERT INTO item_kind_metadata_tv (id, genres, color)
        SELECT
            s.metadata_id,
            CASE
                WHEN jsonb_typeof(s.normalized->'genres') = 'array'
                THEN ARRAY(SELECT jsonb_array_elements_text(s.normalized->'genres'))
                ELSE NULL
            END,
            NULLIF(BTRIM(s.normalized->>'color'), '')
        FROM source AS s
        WHERE s.kind = 'tv'
        ON CONFLICT (id)
        DO UPDATE SET
            genres = COALESCE(EXCLUDED.genres, item_kind_metadata_tv.genres),
            color = COALESCE(EXCLUDED.color, item_kind_metadata_tv.color)
        """
    )


def downgrade() -> None:
    # No destructive rollback required: this migration only backfills typed rows.
    pass
