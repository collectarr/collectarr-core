"""Add tv v1 relational series/season/episode module.

Revision ID: 20260625_2600
Revises: 20260625_2500
Create Date: 2026-06-25 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_2600"
down_revision: str | None = "20260625_2500"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tv_series",
        sa.Column("generic_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_language", sa.String(length=16), nullable=True),
        sa.Column("original_air_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("season_count", sa.Integer(), nullable=True),
        sa.Column("episode_count", sa.Integer(), nullable=True),
        sa.Column("network", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id"),
    )
    op.create_index("ix_tv_series_generic_item_id", "tv_series", ["generic_item_id"], unique=False)
    op.create_index("ix_tv_series_title", "tv_series", ["title"], unique=False)
    op.create_index("ix_tv_series_sort_title", "tv_series", ["sort_title"], unique=False)
    op.create_index("ix_tv_series_original_language", "tv_series", ["original_language"], unique=False)
    op.create_index("ix_tv_series_original_air_date", "tv_series", ["original_air_date"], unique=False)
    op.create_index("ix_tv_series_end_date", "tv_series", ["end_date"], unique=False)
    op.create_index("ix_tv_series_status", "tv_series", ["status"], unique=False)
    op.create_index("ix_tv_series_network", "tv_series", ["network"], unique=False)

    op.create_table(
        "tv_seasons",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=True),
        sa.Column("air_date", sa.Date(), nullable=True),
        sa.Column("episode_count", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["tv_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("series_id", "season_number", name="uq_tv_seasons_series_season"),
    )
    op.create_index("ix_tv_seasons_series_id", "tv_seasons", ["series_id"], unique=False)
    op.create_index("ix_tv_seasons_season_number", "tv_seasons", ["season_number"], unique=False)
    op.create_index("ix_tv_seasons_air_date", "tv_seasons", ["air_date"], unique=False)
    op.create_index(
        "ix_tv_seasons_series_season_number",
        "tv_seasons",
        ["series_id", "season_number"],
        unique=False,
    )

    op.create_table(
        "tv_episodes",
        sa.Column("season_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generic_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("episode_number", sa.String(length=64), nullable=True),
        sa.Column("episode_title", sa.String(length=255), nullable=True),
        sa.Column("air_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["season_id"], ["tv_seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id", name="uq_tv_episodes_generic_item_id"),
    )
    op.create_index("ix_tv_episodes_season_id", "tv_episodes", ["season_id"], unique=False)
    op.create_index("ix_tv_episodes_generic_item_id", "tv_episodes", ["generic_item_id"], unique=False)
    op.create_index("ix_tv_episodes_episode_number", "tv_episodes", ["episode_number"], unique=False)
    op.create_index("ix_tv_episodes_air_date", "tv_episodes", ["air_date"], unique=False)
    op.create_index(
        "ix_tv_episodes_season_episode_number",
        "tv_episodes",
        ["season_id", "episode_number"],
        unique=False,
    )
    op.create_index(
        "ix_tv_episodes_season_air_date",
        "tv_episodes",
        ["season_id", "air_date"],
        unique=False,
    )

    op.create_table(
        "tv_contributions",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("episode_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((series_id IS NOT NULL AND episode_id IS NULL) OR (series_id IS NULL AND episode_id IS NOT NULL))",
            name="ck_tv_contributions_series_xor_episode",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["tv_episodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["series_id"], ["tv_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tv_contributions_series_id", "tv_contributions", ["series_id"], unique=False)
    op.create_index("ix_tv_contributions_episode_id", "tv_contributions", ["episode_id"], unique=False)
    op.create_index("ix_tv_contributions_person_id", "tv_contributions", ["person_id"], unique=False)
    op.create_index("ix_tv_contributions_role", "tv_contributions", ["role"], unique=False)
    op.create_index(
        "ix_tv_contributions_series_role_sequence",
        "tv_contributions",
        ["series_id", "role", "sequence"],
        unique=False,
    )
    op.create_index(
        "ix_tv_contributions_episode_role_sequence",
        "tv_contributions",
        ["episode_id", "role", "sequence"],
        unique=False,
    )

    op.create_table(
        "tv_identifiers",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identifier_type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column(
            "source_provider",
            sa.Enum(
                "comicvine",
                "gcd",
                "anilist",
                "tmdb",
                "openlibrary",
                "igdb",
                "bgg",
                "musicbrainz",
                "hardcover",
                "mangadex",
                name="external_provider",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["tv_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "series_id",
            "identifier_type",
            "normalized_value",
            name="uq_tv_identifiers_series_type_normalized",
        ),
    )
    op.create_index("ix_tv_identifiers_series_id", "tv_identifiers", ["series_id"], unique=False)
    op.create_index("ix_tv_identifiers_identifier_type", "tv_identifiers", ["identifier_type"], unique=False)
    op.create_index("ix_tv_identifiers_source_provider", "tv_identifiers", ["source_provider"], unique=False)
    op.create_index(
        "ix_tv_identifiers_type_value",
        "tv_identifiers",
        ["identifier_type", "normalized_value"],
        unique=False,
    )

    op.create_table(
        "tv_character_appearances",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["series_id"], ["tv_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "series_id",
            "character_id",
            "role",
            name="uq_tv_character_appearances_series_character_role",
        ),
    )
    op.create_index("ix_tv_character_appearances_series_id", "tv_character_appearances", ["series_id"], unique=False)
    op.create_index(
        "ix_tv_character_appearances_character_id", "tv_character_appearances", ["character_id"], unique=False
    )
    op.create_index("ix_tv_character_appearances_role", "tv_character_appearances", ["role"], unique=False)
    op.create_index(
        "ix_tv_character_appearances_series_role",
        "tv_character_appearances",
        ["series_id", "role"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO tv_series (
            id,
            generic_item_id,
            title,
            sort_title,
            description,
            original_language,
            original_air_date,
            end_date,
            status,
            season_count,
            episode_count,
            network,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            i.id,
            i.title,
            NULLIF(trim(i.sort_key), ''),
            COALESCE(i.plot_description, i.plot_summary, i.synopsis),
            NULLIF(trim(i.metadata_json->>'original_language'), ''),
            CASE
                WHEN (i.metadata_json->>'original_air_date') ~ '^\\d{4}-\\d{2}-\\d{2}$'
                THEN (i.metadata_json->>'original_air_date')::date
                ELSE NULL
            END,
            CASE
                WHEN (i.metadata_json->>'end_date') ~ '^\\d{4}-\\d{2}-\\d{2}$'
                THEN (i.metadata_json->>'end_date')::date
                ELSE NULL
            END,
            NULLIF(trim(i.metadata_json->>'status'), ''),
            (i.metadata_json->>'season_count')::integer,
            (i.metadata_json->>'episode_count')::integer,
            NULLIF(trim(i.metadata_json->>'network'), ''),
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        WHERE i.kind = 'tv'
          AND NOT EXISTS (
              SELECT 1 FROM tv_series ts WHERE ts.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        INSERT INTO tv_seasons (
            id,
            series_id,
            season_number,
            air_date,
            episode_count,
            description,
            cover_image_url,
            cover_image_key,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            ts.id,
            COALESCE((i.metadata_json->>'season_number')::integer, 1),
            e.release_date,
            NULL,
            NULL,
            NULL,
            NULL,
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        JOIN tv_series ts ON ts.generic_item_id = i.id
        LEFT JOIN LATERAL (
            SELECT e2.*
            FROM editions e2
            WHERE e2.item_id = i.id
            ORDER BY e2.release_date ASC NULLS LAST, e2.created_at ASC, e2.id ASC
            LIMIT 1
        ) e ON TRUE
        ON CONFLICT (series_id, season_number) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO tv_episodes (
            id,
            season_id,
            generic_item_id,
            episode_number,
            episode_title,
            air_date,
            description,
            cover_image_url,
            cover_image_key,
            runtime_minutes,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            tseason.id,
            i.id,
            NULLIF(trim(i.item_number), ''),
            NULLIF(trim(COALESCE(e.title, i.title)), ''),
            e.release_date,
            COALESCE(i.plot_description, i.plot_summary, i.synopsis),
            primary_variant.cover_image_url,
            primary_variant.cover_image_key,
            i.runtime_minutes,
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        JOIN tv_series ts ON ts.generic_item_id = i.id
        JOIN tv_seasons tseason ON tseason.series_id = ts.id
        LEFT JOIN LATERAL (
            SELECT e2.*
            FROM editions e2
            WHERE e2.item_id = i.id
            ORDER BY e2.release_date ASC NULLS LAST, e2.created_at ASC, e2.id ASC
            LIMIT 1
        ) e ON TRUE
        LEFT JOIN LATERAL (
            SELECT v.*
            FROM variants v
            WHERE e.id IS NOT NULL AND v.edition_id = e.id
            ORDER BY v.is_primary DESC, v.created_at ASC, v.id ASC
            LIMIT 1
        ) primary_variant ON TRUE
        WHERE i.kind = 'tv'
          AND tseason.season_number = COALESCE((i.metadata_json->>'season_number')::integer, 1)
          AND NOT EXISTS (
              SELECT 1 FROM tv_episodes te WHERE te.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        INSERT INTO tv_contributions (
            id,
            series_id,
            episode_id,
            person_id,
            role,
            sequence,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            NULL,
            te.id,
            ep.person_id,
            ep.role,
            row_number() OVER (
                PARTITION BY te.id, ep.role
                ORDER BY ep.created_at ASC, ep.id ASC
            ),
            NULL,
            now(),
            now()
        FROM entity_persons ep
        JOIN tv_episodes te ON te.generic_item_id = ep.entity_id
        WHERE ep.entity_type = 'item'
        """
    )

    op.execute(
        """
        INSERT INTO tv_character_appearances (
            id,
            series_id,
            character_id,
            role,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            ts.id,
            ca.character_id,
            ca.role,
            NULL,
            now(),
            now()
        FROM character_appearances ca
        JOIN tv_episodes te ON te.generic_item_id = ca.item_id
        JOIN tv_series ts ON ts.id = (
            SELECT series_id FROM tv_seasons WHERE id = te.season_id
        )
        WHERE ca.item_kind = 'tv'
        ON CONFLICT (series_id, character_id, role) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO tv_identifiers (
            id,
            series_id,
            identifier_type,
            value,
            normalized_value,
            is_primary,
            source_provider,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            ts.id,
            'provider_item_id',
            ipl.provider_item_id,
            regexp_replace(lower(ipl.provider_item_id), '[^a-z0-9]+', '', 'g'),
            FALSE,
            ipl.provider,
            NULL,
            now(),
            now()
        FROM tv_series ts
        JOIN item_provider_links ipl ON ipl.item_id = ts.generic_item_id
        WHERE ipl.provider_item_id IS NOT NULL AND trim(ipl.provider_item_id) <> ''
        ON CONFLICT (series_id, identifier_type, normalized_value) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("tv_character_appearances")
    op.drop_table("tv_identifiers")
    op.drop_table("tv_contributions")
    op.drop_table("tv_episodes")
    op.drop_table("tv_seasons")
    op.drop_table("tv_series")
