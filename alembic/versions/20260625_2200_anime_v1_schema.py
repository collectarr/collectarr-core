"""Add anime v1 relational series/episode module.

Revision ID: 20260625_2200
Revises: 20260625_2100
Create Date: 2026-06-25 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_2200"
down_revision: str | None = "20260625_2100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anime_series",
        sa.Column("generic_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_language", sa.String(length=16), nullable=True),
        sa.Column("original_air_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("anime_type", sa.String(length=64), nullable=True),
        sa.Column("episode_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id"),
    )
    op.create_index("ix_anime_series_generic_item_id", "anime_series", ["generic_item_id"], unique=False)
    op.create_index("ix_anime_series_title", "anime_series", ["title"], unique=False)
    op.create_index("ix_anime_series_sort_title", "anime_series", ["sort_title"], unique=False)
    op.create_index("ix_anime_series_original_language", "anime_series", ["original_language"], unique=False)
    op.create_index("ix_anime_series_original_air_date", "anime_series", ["original_air_date"], unique=False)
    op.create_index("ix_anime_series_end_date", "anime_series", ["end_date"], unique=False)
    op.create_index("ix_anime_series_status", "anime_series", ["status"], unique=False)
    op.create_index("ix_anime_series_anime_type", "anime_series", ["anime_type"], unique=False)

    op.create_table(
        "anime_episodes",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["series_id"], ["anime_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id", name="uq_anime_episodes_generic_item_id"),
    )
    op.create_index("ix_anime_episodes_series_id", "anime_episodes", ["series_id"], unique=False)
    op.create_index("ix_anime_episodes_generic_item_id", "anime_episodes", ["generic_item_id"], unique=False)
    op.create_index("ix_anime_episodes_episode_number", "anime_episodes", ["episode_number"], unique=False)
    op.create_index("ix_anime_episodes_air_date", "anime_episodes", ["air_date"], unique=False)
    op.create_index(
        "ix_anime_episodes_series_episode_number",
        "anime_episodes",
        ["series_id", "episode_number"],
        unique=False,
    )
    op.create_index(
        "ix_anime_episodes_series_air_date",
        "anime_episodes",
        ["series_id", "air_date"],
        unique=False,
    )

    op.create_table(
        "anime_contributions",
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
            name="ck_anime_contributions_series_xor_episode",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["anime_episodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["series_id"], ["anime_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anime_contributions_series_id", "anime_contributions", ["series_id"], unique=False)
    op.create_index("ix_anime_contributions_episode_id", "anime_contributions", ["episode_id"], unique=False)
    op.create_index("ix_anime_contributions_person_id", "anime_contributions", ["person_id"], unique=False)
    op.create_index("ix_anime_contributions_role", "anime_contributions", ["role"], unique=False)
    op.create_index(
        "ix_anime_contributions_series_role_sequence",
        "anime_contributions",
        ["series_id", "role", "sequence"],
        unique=False,
    )
    op.create_index(
        "ix_anime_contributions_episode_role_sequence",
        "anime_contributions",
        ["episode_id", "role", "sequence"],
        unique=False,
    )

    op.create_table(
        "anime_identifiers",
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
        sa.ForeignKeyConstraint(["series_id"], ["anime_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "series_id",
            "identifier_type",
            "normalized_value",
            name="uq_anime_identifiers_series_type_normalized",
        ),
    )
    op.create_index("ix_anime_identifiers_series_id", "anime_identifiers", ["series_id"], unique=False)
    op.create_index("ix_anime_identifiers_identifier_type", "anime_identifiers", ["identifier_type"], unique=False)
    op.create_index("ix_anime_identifiers_source_provider", "anime_identifiers", ["source_provider"], unique=False)
    op.create_index(
        "ix_anime_identifiers_type_value",
        "anime_identifiers",
        ["identifier_type", "normalized_value"],
        unique=False,
    )

    op.create_table(
        "anime_character_appearances",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["series_id"], ["anime_series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "series_id",
            "character_id",
            "role",
            name="uq_anime_character_appearances_series_character_role",
        ),
    )
    op.create_index("ix_anime_character_appearances_series_id", "anime_character_appearances", ["series_id"], unique=False)
    op.create_index(
        "ix_anime_character_appearances_character_id", "anime_character_appearances", ["character_id"], unique=False
    )
    op.create_index("ix_anime_character_appearances_role", "anime_character_appearances", ["role"], unique=False)
    op.create_index(
        "ix_anime_character_appearances_series_role",
        "anime_character_appearances",
        ["series_id", "role"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO anime_series (
            id,
            generic_item_id,
            title,
            sort_title,
            description,
            original_language,
            original_air_date,
            end_date,
            status,
            anime_type,
            episode_count,
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
            NULLIF(trim(i.metadata_json->>'anime_type'), ''),
            (i.metadata_json->>'episode_count')::integer,
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        WHERE i.kind = 'anime'
          AND NOT EXISTS (
              SELECT 1 FROM anime_series aseries WHERE aseries.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        INSERT INTO anime_episodes (
            id,
            series_id,
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
            aseries.id,
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
        JOIN anime_series aseries ON aseries.generic_item_id = i.id
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
        WHERE i.kind = 'anime'
          AND NOT EXISTS (
              SELECT 1 FROM anime_episodes ae WHERE ae.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        INSERT INTO anime_contributions (
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
            ae.id,
            ep.person_id,
            ep.role,
            row_number() OVER (
                PARTITION BY ae.id, ep.role
                ORDER BY ep.created_at ASC, ep.id ASC
            ),
            NULL,
            now(),
            now()
        FROM entity_persons ep
        JOIN anime_episodes ae ON ae.generic_item_id = ep.entity_id
        WHERE ep.entity_type = 'item'
        """
    )

    op.execute(
        """
        INSERT INTO anime_character_appearances (
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
            aseries.id,
            ca.character_id,
            ca.role,
            NULL,
            now(),
            now()
        FROM character_appearances ca
        JOIN anime_episodes ae ON ae.generic_item_id = ca.item_id
        JOIN anime_series aseries ON aseries.id = ae.series_id
        WHERE ca.item_kind = 'anime'
        ON CONFLICT (series_id, character_id, role) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO anime_identifiers (
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
            aseries.id,
            'provider_item_id',
            ipl.provider_item_id,
            regexp_replace(lower(ipl.provider_item_id), '[^a-z0-9]+', '', 'g'),
            FALSE,
            ipl.provider,
            NULL,
            now(),
            now()
        FROM anime_episodes ae
        JOIN anime_series aseries ON aseries.id = ae.series_id
        JOIN item_provider_links ipl ON ipl.item_id = ae.generic_item_id
        WHERE ipl.provider_item_id IS NOT NULL AND trim(ipl.provider_item_id) <> ''
        ON CONFLICT (series_id, identifier_type, normalized_value) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("anime_character_appearances")
    op.drop_table("anime_identifiers")
    op.drop_table("anime_contributions")
    op.drop_table("anime_episodes")
    op.drop_table("anime_series")
