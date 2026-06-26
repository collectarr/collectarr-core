"""Add manga v1 relational work/chapter module.

Revision ID: 20260625_2000
Revises: 20260625_1900
Create Date: 2026-06-25 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_2000"
down_revision: str | None = "20260625_1900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "manga_works",
        sa.Column("generic_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_title", sa.String(length=255), nullable=True),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_language", sa.String(length=16), nullable=True),
        sa.Column("original_publication_date", sa.Date(), nullable=True),
        sa.Column("first_publication_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id"),
    )
    op.create_index("ix_manga_works_generic_item_id", "manga_works", ["generic_item_id"], unique=False)
    op.create_index("ix_manga_works_title", "manga_works", ["title"], unique=False)
    op.create_index("ix_manga_works_sort_title", "manga_works", ["sort_title"], unique=False)
    op.create_index("ix_manga_works_original_language", "manga_works", ["original_language"], unique=False)
    op.create_index(
        "ix_manga_works_original_publication_date",
        "manga_works",
        ["original_publication_date"],
        unique=False,
    )
    op.create_index("ix_manga_works_first_publication_date", "manga_works", ["first_publication_date"], unique=False)
    op.create_index("ix_manga_works_status", "manga_works", ["status"], unique=False)

    op.create_table(
        "manga_chapters",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generic_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chapter_number", sa.String(length=64), nullable=True),
        sa.Column("chapter_title", sa.String(length=255), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["work_id"], ["manga_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id", name="uq_manga_chapters_generic_item_id"),
    )
    op.create_index("ix_manga_chapters_work_id", "manga_chapters", ["work_id"], unique=False)
    op.create_index("ix_manga_chapters_generic_item_id", "manga_chapters", ["generic_item_id"], unique=False)
    op.create_index("ix_manga_chapters_chapter_number", "manga_chapters", ["chapter_number"], unique=False)
    op.create_index("ix_manga_chapters_publication_date", "manga_chapters", ["publication_date"], unique=False)
    op.create_index(
        "ix_manga_chapters_work_chapter_number",
        "manga_chapters",
        ["work_id", "chapter_number"],
        unique=False,
    )
    op.create_index(
        "ix_manga_chapters_work_publication",
        "manga_chapters",
        ["work_id", "publication_date"],
        unique=False,
    )

    op.create_table(
        "manga_contributions",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((work_id IS NOT NULL AND chapter_id IS NULL) OR (work_id IS NULL AND chapter_id IS NOT NULL))",
            name="ck_manga_contributions_work_xor_chapter",
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["manga_chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["manga_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manga_contributions_work_id", "manga_contributions", ["work_id"], unique=False)
    op.create_index("ix_manga_contributions_chapter_id", "manga_contributions", ["chapter_id"], unique=False)
    op.create_index("ix_manga_contributions_person_id", "manga_contributions", ["person_id"], unique=False)
    op.create_index("ix_manga_contributions_role", "manga_contributions", ["role"], unique=False)
    op.create_index(
        "ix_manga_contributions_work_role_sequence",
        "manga_contributions",
        ["work_id", "role", "sequence"],
        unique=False,
    )
    op.create_index(
        "ix_manga_contributions_chapter_role_sequence",
        "manga_contributions",
        ["chapter_id", "role", "sequence"],
        unique=False,
    )

    op.create_table(
        "manga_identifiers",
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
        sa.ForeignKeyConstraint(["work_id"], ["manga_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_id",
            "identifier_type",
            "normalized_value",
            name="uq_manga_identifiers_work_type_normalized",
        ),
    )
    op.create_index("ix_manga_identifiers_work_id", "manga_identifiers", ["work_id"], unique=False)
    op.create_index("ix_manga_identifiers_identifier_type", "manga_identifiers", ["identifier_type"], unique=False)
    op.create_index("ix_manga_identifiers_source_provider", "manga_identifiers", ["source_provider"], unique=False)
    op.create_index(
        "ix_manga_identifiers_type_value",
        "manga_identifiers",
        ["identifier_type", "normalized_value"],
        unique=False,
    )

    op.create_table(
        "manga_character_appearances",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["manga_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_id",
            "character_id",
            "role",
            name="uq_manga_character_appearances_work_character_role",
        ),
    )
    op.create_index("ix_manga_character_appearances_work_id", "manga_character_appearances", ["work_id"], unique=False)
    op.create_index(
        "ix_manga_character_appearances_character_id", "manga_character_appearances", ["character_id"], unique=False
    )
    op.create_index("ix_manga_character_appearances_role", "manga_character_appearances", ["role"], unique=False)
    op.create_index(
        "ix_manga_character_appearances_work_role",
        "manga_character_appearances",
        ["work_id", "role"],
        unique=False,
    )

    op.create_table(
        "manga_series_memberships",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Float(), nullable=True),
        sa.Column("display_number", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["manga_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "series_id", name="uq_manga_series_memberships_work_series"),
    )
    op.create_index("ix_manga_series_memberships_work_id", "manga_series_memberships", ["work_id"], unique=False)
    op.create_index("ix_manga_series_memberships_series_id", "manga_series_memberships", ["series_id"], unique=False)
    op.create_index(
        "ix_manga_series_memberships_series_sequence",
        "manga_series_memberships",
        ["series_id", "sequence"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO manga_works (
            id,
            generic_item_id,
            title,
            sort_title,
            subtitle,
            description,
            original_language,
            original_publication_date,
            first_publication_date,
            status,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            i.id,
            i.title,
            NULLIF(trim(i.sort_key), ''),
            NULL,
            COALESCE(i.plot_description, i.plot_summary, i.synopsis),
            NULLIF(trim(i.metadata_json->>'original_language'), ''),
            CASE
                WHEN (i.metadata_json->>'original_publication_date') ~ '^\\d{4}-\\d{2}-\\d{2}$'
                THEN (i.metadata_json->>'original_publication_date')::date
                ELSE NULL
            END,
            CASE
                WHEN (i.metadata_json->>'first_publication_date') ~ '^\\d{4}-\\d{2}-\\d{2}$'
                THEN (i.metadata_json->>'first_publication_date')::date
                ELSE NULL
            END,
            NULLIF(trim(i.metadata_json->>'status'), ''),
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        WHERE i.kind = 'manga'
          AND NOT EXISTS (
              SELECT 1 FROM manga_works mw WHERE mw.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        INSERT INTO manga_chapters (
            id,
            work_id,
            generic_item_id,
            chapter_number,
            chapter_title,
            publication_date,
            page_count,
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
            NULLIF(trim(i.item_number), ''),
            NULLIF(trim(COALESCE(e.title, i.title)), ''),
            e.release_date,
            i.page_count,
            COALESCE(i.plot_description, i.plot_summary, i.synopsis),
            primary_variant.cover_image_url,
            primary_variant.cover_image_key,
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        JOIN manga_works mw ON mw.generic_item_id = i.id
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
        WHERE i.kind = 'manga'
          AND NOT EXISTS (
              SELECT 1 FROM manga_chapters mc WHERE mc.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        UPDATE manga_works mw
        SET first_publication_date = src.first_publication_date
        FROM (
            SELECT mc.work_id, MIN(mc.publication_date) AS first_publication_date
            FROM manga_chapters mc
            GROUP BY mc.work_id
        ) src
        WHERE src.work_id = mw.id
        """
    )

    op.execute(
        """
        INSERT INTO manga_contributions (
            id,
            work_id,
            chapter_id,
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
            mc.id,
            ep.person_id,
            ep.role,
            row_number() OVER (
                PARTITION BY mc.id, ep.role
                ORDER BY ep.created_at ASC, ep.id ASC
            ),
            NULL,
            now(),
            now()
        FROM entity_persons ep
        JOIN manga_chapters mc ON mc.generic_item_id = ep.entity_id
        WHERE ep.entity_type = 'item'
        """
    )

    op.execute(
        """
        INSERT INTO manga_character_appearances (
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
        JOIN manga_chapters mc ON mc.generic_item_id = ca.item_id
        JOIN manga_works mw ON mw.id = mc.work_id
        WHERE ca.item_kind = 'manga'
        ON CONFLICT (work_id, character_id, role) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO manga_identifiers (
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
            CASE
                WHEN length(regexp_replace(e.isbn, '[^0-9Xx]', '', 'g')) = 10 THEN 'isbn10'
                WHEN length(regexp_replace(e.isbn, '[^0-9Xx]', '', 'g')) = 13 THEN 'isbn13'
                ELSE 'isbn13'
            END,
            e.isbn,
            regexp_replace(lower(e.isbn), '[^0-9x]+', '', 'g'),
            TRUE,
            NULL,
            NULL,
            now(),
            now()
        FROM manga_chapters mc
        JOIN manga_works mw ON mw.id = mc.work_id
        JOIN items i ON i.id = mc.generic_item_id
        JOIN editions e ON e.item_id = i.id
        WHERE e.isbn IS NOT NULL AND trim(e.isbn) <> ''
        ON CONFLICT (work_id, identifier_type, normalized_value) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO manga_identifiers (
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
            CASE
                WHEN length(regexp_replace(v.barcode, '[^0-9]', '', 'g')) = 13 THEN 'ean'
                ELSE 'upc'
            END,
            v.barcode,
            regexp_replace(lower(v.barcode), '[^0-9]+', '', 'g'),
            FALSE,
            NULL,
            NULL,
            now(),
            now()
        FROM manga_chapters mc
        JOIN manga_works mw ON mw.id = mc.work_id
        JOIN items i ON i.id = mc.generic_item_id
        JOIN editions e ON e.item_id = i.id
        JOIN variants v ON v.edition_id = e.id
        WHERE v.barcode IS NOT NULL AND trim(v.barcode) <> ''
        ON CONFLICT (work_id, identifier_type, normalized_value) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO manga_identifiers (
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
        FROM manga_chapters mc
        JOIN manga_works mw ON mw.id = mc.work_id
        JOIN item_provider_links ipl ON ipl.item_id = mc.generic_item_id
        WHERE ipl.provider_item_id IS NOT NULL AND trim(ipl.provider_item_id) <> ''
        ON CONFLICT (work_id, identifier_type, normalized_value) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO manga_series_memberships (
            id,
            work_id,
            series_id,
            sequence,
            display_number,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            mw.id,
            s.id,
            NULL,
            NULL,
            NULL,
            now(),
            now()
        FROM manga_works mw
        JOIN items i ON i.id = mw.generic_item_id
        JOIN volumes v ON v.id = i.volume_id
        JOIN series s ON s.id = v.series_id
        ON CONFLICT (work_id, series_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("manga_series_memberships")
    op.drop_table("manga_character_appearances")
    op.drop_table("manga_identifiers")
    op.drop_table("manga_contributions")
    op.drop_table("manga_chapters")
    op.drop_table("manga_works")
