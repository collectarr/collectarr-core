"""Add movie v1 relational work/release module.

Revision ID: 20260625_2400
Revises: 20260625_2300
Create Date: 2026-06-25 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_2400"
down_revision: str | None = "20260625_2300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movie_works",
        sa.Column("generic_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_language", sa.String(length=16), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id"),
    )
    op.create_index("ix_movie_works_generic_item_id", "movie_works", ["generic_item_id"], unique=False)
    op.create_index("ix_movie_works_title", "movie_works", ["title"], unique=False)
    op.create_index("ix_movie_works_sort_title", "movie_works", ["sort_title"], unique=False)
    op.create_index("ix_movie_works_original_language", "movie_works", ["original_language"], unique=False)
    op.create_index("ix_movie_works_release_date", "movie_works", ["release_date"], unique=False)

    op.create_table(
        "movie_releases",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generic_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("release_title", sa.String(length=255), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("format", sa.String(length=100), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["work_id"], ["movie_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id", name="uq_movie_releases_generic_item_id"),
    )
    op.create_index("ix_movie_releases_work_id", "movie_releases", ["work_id"], unique=False)
    op.create_index("ix_movie_releases_generic_item_id", "movie_releases", ["generic_item_id"], unique=False)
    op.create_index("ix_movie_releases_release_date", "movie_releases", ["release_date"], unique=False)
    op.create_index("ix_movie_releases_region", "movie_releases", ["region"], unique=False)
    op.create_index("ix_movie_releases_format", "movie_releases", ["format"], unique=False)
    op.create_index("ix_movie_releases_language", "movie_releases", ["language"], unique=False)
    op.create_index(
        "ix_movie_releases_work_region",
        "movie_releases",
        ["work_id", "region"],
        unique=False,
    )

    op.create_table(
        "movie_contributions",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["movie_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_movie_contributions_work_id", "movie_contributions", ["work_id"], unique=False)
    op.create_index("ix_movie_contributions_person_id", "movie_contributions", ["person_id"], unique=False)
    op.create_index("ix_movie_contributions_role", "movie_contributions", ["role"], unique=False)
    op.create_index(
        "ix_movie_contributions_work_role_sequence",
        "movie_contributions",
        ["work_id", "role", "sequence"],
        unique=False,
    )

    op.create_table(
        "movie_identifiers",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["work_id"], ["movie_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_id",
            "identifier_type",
            "normalized_value",
            name="uq_movie_identifiers_work_type_normalized",
        ),
    )
    op.create_index("ix_movie_identifiers_work_id", "movie_identifiers", ["work_id"], unique=False)
    op.create_index("ix_movie_identifiers_identifier_type", "movie_identifiers", ["identifier_type"], unique=False)
    op.create_index("ix_movie_identifiers_source_provider", "movie_identifiers", ["source_provider"], unique=False)
    op.create_index(
        "ix_movie_identifiers_type_value",
        "movie_identifiers",
        ["identifier_type", "normalized_value"],
        unique=False,
    )

    op.create_table(
        "movie_character_appearances",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["movie_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_id",
            "character_id",
            "role",
            name="uq_movie_character_appearances_work_character_role",
        ),
    )
    op.create_index("ix_movie_character_appearances_work_id", "movie_character_appearances", ["work_id"], unique=False)
    op.create_index(
        "ix_movie_character_appearances_character_id", "movie_character_appearances", ["character_id"], unique=False
    )
    op.create_index("ix_movie_character_appearances_role", "movie_character_appearances", ["role"], unique=False)
    op.create_index(
        "ix_movie_character_appearances_work_role",
        "movie_character_appearances",
        ["work_id", "role"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO movie_works (
            id,
            generic_item_id,
            title,
            sort_title,
            description,
            original_language,
            release_date,
            runtime_minutes,
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
                WHEN (i.metadata_json->>'release_date') ~ '^\\d{4}-\\d{2}-\\d{2}$'
                THEN (i.metadata_json->>'release_date')::date
                ELSE NULL
            END,
            i.runtime_minutes,
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        WHERE i.kind = 'movie'
          AND NOT EXISTS (
              SELECT 1 FROM movie_works mw WHERE mw.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        INSERT INTO movie_releases (
            id,
            work_id,
            generic_item_id,
            release_title,
            release_date,
            region,
            format,
            language,
            description,
            cover_image_url,
            cover_image_key,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            mw.id,
            i.id,
            NULLIF(trim(COALESCE(e.title, i.title)), ''),
            e.release_date,
            e.region,
            e.format,
            e.language,
            COALESCE(i.plot_description, i.plot_summary, i.synopsis),
            primary_variant.cover_image_url,
            primary_variant.cover_image_key,
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        JOIN movie_works mw ON mw.generic_item_id = i.id
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
        WHERE i.kind = 'movie'
          AND NOT EXISTS (
              SELECT 1 FROM movie_releases mr WHERE mr.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        INSERT INTO movie_contributions (
            id,
            work_id,
            person_id,
            role,
            sequence,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            mw.id,
            ep.person_id,
            ep.role,
            row_number() OVER (
                PARTITION BY mw.id, ep.role
                ORDER BY ep.created_at ASC, ep.id ASC
            ),
            NULL,
            now(),
            now()
        FROM entity_persons ep
        JOIN movie_works mw ON mw.generic_item_id = ep.entity_id
        WHERE ep.entity_type = 'item'
        """
    )

    op.execute(
        """
        INSERT INTO movie_character_appearances (
            id,
            work_id,
            character_id,
            role,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            mw.id,
            ca.character_id,
            ca.role,
            NULL,
            now(),
            now()
        FROM character_appearances ca
        JOIN movie_works mw ON mw.generic_item_id = ca.item_id
        WHERE ca.item_kind = 'movie'
        ON CONFLICT (work_id, character_id, role) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO movie_identifiers (
            id,
            work_id,
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
            mw.id,
            'provider_item_id',
            ipl.provider_item_id,
            regexp_replace(lower(ipl.provider_item_id), '[^a-z0-9]+', '', 'g'),
            FALSE,
            ipl.provider,
            NULL,
            now(),
            now()
        FROM movie_works mw
        JOIN item_provider_links ipl ON ipl.item_id = mw.generic_item_id
        WHERE ipl.provider_item_id IS NOT NULL AND trim(ipl.provider_item_id) <> ''
        ON CONFLICT (work_id, identifier_type, normalized_value) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("movie_character_appearances")
    op.drop_table("movie_identifiers")
    op.drop_table("movie_contributions")
    op.drop_table("movie_releases")
    op.drop_table("movie_works")
