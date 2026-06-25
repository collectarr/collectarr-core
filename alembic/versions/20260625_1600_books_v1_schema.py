"""Add books v1 relational work/edition module.

Revision ID: 20260625_1600
Revises: 20260625_1500
Create Date: 2026-06-25 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_1600"
down_revision: str | None = "20260625_1500"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "book_works",
        sa.Column("generic_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_title", sa.String(length=255), nullable=True),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_language", sa.String(length=16), nullable=True),
        sa.Column("original_publication_date", sa.Date(), nullable=True),
        sa.Column("first_publication_date", sa.Date(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id"),
    )
    op.create_index("ix_book_works_generic_item_id", "book_works", ["generic_item_id"], unique=False)
    op.create_index("ix_book_works_title", "book_works", ["title"], unique=False)
    op.create_index("ix_book_works_sort_title", "book_works", ["sort_title"], unique=False)
    op.create_index("ix_book_works_original_language", "book_works", ["original_language"], unique=False)
    op.create_index(
        "ix_book_works_original_publication_date",
        "book_works",
        ["original_publication_date"],
        unique=False,
    )
    op.create_index("ix_book_works_first_publication_date", "book_works", ["first_publication_date"], unique=False)

    op.create_table(
        "book_editions",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generic_edition_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_title", sa.String(length=255), nullable=True),
        sa.Column("edition_statement", sa.String(length=255), nullable=True),
        sa.Column("format", sa.String(length=100), nullable=True),
        sa.Column("binding", sa.String(length=100), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("imprint", sa.String(length=255), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("audio_length_minutes", sa.Integer(), nullable=True),
        sa.Column("age_rating", sa.String(length=64), nullable=True),
        sa.Column("release_status", sa.String(length=64), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_edition_id"], ["editions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["work_id"], ["book_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_edition_id"),
    )
    op.create_index("ix_book_editions_work_id", "book_editions", ["work_id"], unique=False)
    op.create_index("ix_book_editions_generic_edition_id", "book_editions", ["generic_edition_id"], unique=False)
    op.create_index("ix_book_editions_format", "book_editions", ["format"], unique=False)
    op.create_index("ix_book_editions_binding", "book_editions", ["binding"], unique=False)
    op.create_index("ix_book_editions_publication_date", "book_editions", ["publication_date"], unique=False)
    op.create_index("ix_book_editions_publisher", "book_editions", ["publisher"], unique=False)
    op.create_index("ix_book_editions_imprint", "book_editions", ["imprint"], unique=False)
    op.create_index("ix_book_editions_language", "book_editions", ["language"], unique=False)
    op.create_index("ix_book_editions_region", "book_editions", ["region"], unique=False)
    op.create_index("ix_book_editions_age_rating", "book_editions", ["age_rating"], unique=False)
    op.create_index("ix_book_editions_release_status", "book_editions", ["release_status"], unique=False)
    op.create_index(
        "ix_book_editions_work_publication",
        "book_editions",
        ["work_id", "publication_date"],
        unique=False,
    )

    op.create_table(
        "book_printings",
        sa.Column("edition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("printing_number", sa.Integer(), nullable=True),
        sa.Column("printing_statement", sa.String(length=255), nullable=True),
        sa.Column("print_run", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["edition_id"], ["book_editions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_book_printings_edition_id", "book_printings", ["edition_id"], unique=False)
    op.create_index("ix_book_printings_printing_number", "book_printings", ["printing_number"], unique=False)

    op.create_table(
        "book_contributions",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("edition_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((work_id IS NOT NULL AND edition_id IS NULL) OR (work_id IS NULL AND edition_id IS NOT NULL))",
            name="ck_book_contributions_work_xor_edition",
        ),
        sa.ForeignKeyConstraint(["edition_id"], ["book_editions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["book_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_book_contributions_work_id", "book_contributions", ["work_id"], unique=False)
    op.create_index("ix_book_contributions_edition_id", "book_contributions", ["edition_id"], unique=False)
    op.create_index("ix_book_contributions_person_id", "book_contributions", ["person_id"], unique=False)
    op.create_index("ix_book_contributions_role", "book_contributions", ["role"], unique=False)
    op.create_index(
        "ix_book_contributions_work_role_sequence",
        "book_contributions",
        ["work_id", "role", "sequence"],
        unique=False,
    )
    op.create_index(
        "ix_book_contributions_edition_role_sequence",
        "book_contributions",
        ["edition_id", "role", "sequence"],
        unique=False,
    )

    op.create_table(
        "book_identifiers",
        sa.Column("edition_id", postgresql.UUID(as_uuid=True), nullable=False),
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
                name="external_provider",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["edition_id"], ["book_editions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "edition_id",
            "identifier_type",
            "normalized_value",
            name="uq_book_identifiers_edition_type_normalized",
        ),
    )
    op.create_index("ix_book_identifiers_edition_id", "book_identifiers", ["edition_id"], unique=False)
    op.create_index("ix_book_identifiers_identifier_type", "book_identifiers", ["identifier_type"], unique=False)
    op.create_index("ix_book_identifiers_source_provider", "book_identifiers", ["source_provider"], unique=False)
    op.create_index(
        "ix_book_identifiers_type_value",
        "book_identifiers",
        ["identifier_type", "normalized_value"],
        unique=False,
    )

    op.create_table(
        "book_series_memberships",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Float(), nullable=True),
        sa.Column("display_number", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["book_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "series_id", name="uq_book_series_memberships_work_series"),
    )
    op.create_index("ix_book_series_memberships_work_id", "book_series_memberships", ["work_id"], unique=False)
    op.create_index("ix_book_series_memberships_series_id", "book_series_memberships", ["series_id"], unique=False)
    op.create_index(
        "ix_book_series_memberships_series_sequence",
        "book_series_memberships",
        ["series_id", "sequence"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO book_works (
            id,
            generic_item_id,
            title,
            sort_title,
            subtitle,
            description,
            original_language,
            original_publication_date,
            first_publication_date,
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
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        WHERE i.kind = 'book'
          AND NOT EXISTS (
              SELECT 1 FROM book_works bw WHERE bw.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        INSERT INTO book_editions (
            id,
            work_id,
            generic_edition_id,
            display_title,
            edition_statement,
            format,
            binding,
            publication_date,
            publisher,
            imprint,
            language,
            region,
            page_count,
            audio_length_minutes,
            age_rating,
            release_status,
            cover_image_url,
            cover_image_key,
            description,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            bw.id,
            e.id,
            NULLIF(trim(COALESCE(e.title, i.title)), ''),
            NULLIF(trim(e.metadata_json->>'edition_statement'), ''),
            e.format,
            NULLIF(trim(e.metadata_json->>'binding'), ''),
            e.release_date,
            e.publisher,
            e.imprint,
            e.language,
            e.region,
            i.page_count,
            CASE
                WHEN lower(COALESCE(e.format, '')) LIKE '%audio%' THEN i.runtime_minutes
                ELSE NULL
            END,
            e.age_rating,
            e.release_status,
            (
                SELECT v.cover_image_url
                FROM variants v
                WHERE v.edition_id = e.id
                ORDER BY v.is_primary DESC, v.created_at ASC
                LIMIT 1
            ),
            (
                SELECT v.cover_image_key
                FROM variants v
                WHERE v.edition_id = e.id
                ORDER BY v.is_primary DESC, v.created_at ASC
                LIMIT 1
            ),
            COALESCE(e.metadata_json->>'description', i.synopsis),
            jsonb_build_object('backfilled_from_edition', e.id::text),
            now(),
            now()
        FROM editions e
        JOIN items i ON i.id = e.item_id
        JOIN book_works bw ON bw.generic_item_id = i.id
        WHERE i.kind = 'book'
          AND NOT EXISTS (
              SELECT 1 FROM book_editions be WHERE be.generic_edition_id = e.id
          )
        """
    )

    op.execute(
        """
        UPDATE book_works bw
        SET subtitle = src.subtitle,
            first_publication_date = COALESCE(
                bw.first_publication_date,
                src.first_publication_date
            )
        FROM (
            SELECT
                be.work_id,
                MIN(be.publication_date) AS first_publication_date,
                MAX(NULLIF(trim(be.edition_statement), '')) AS subtitle
            FROM book_editions be
            GROUP BY be.work_id
        ) src
        WHERE src.work_id = bw.id
        """
    )

    op.execute(
        """
        INSERT INTO book_contributions (
            id,
            work_id,
            edition_id,
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
            be.id,
            ep.person_id,
            ep.role,
            row_number() OVER (
                PARTITION BY be.id, ep.role
                ORDER BY ep.created_at ASC, ep.id ASC
            ),
            NULL,
            now(),
            now()
        FROM entity_persons ep
        JOIN items i ON i.id = ep.entity_id AND ep.entity_type = 'item'
        JOIN editions e ON e.item_id = i.id
        JOIN book_editions be ON be.generic_edition_id = e.id
        WHERE i.kind = 'book'
        """
    )

    op.execute(
        """
        INSERT INTO book_identifiers (
            id,
            edition_id,
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
            be.id,
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
        FROM book_editions be
        JOIN editions e ON e.id = be.generic_edition_id
        WHERE e.isbn IS NOT NULL AND trim(e.isbn) <> ''
        ON CONFLICT (edition_id, identifier_type, normalized_value) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO book_identifiers (
            id,
            edition_id,
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
            be.id,
            CASE
                WHEN length(regexp_replace(e.upc, '[^0-9]', '', 'g')) = 13 THEN 'ean'
                ELSE 'upc'
            END,
            e.upc,
            regexp_replace(lower(e.upc), '[^0-9]+', '', 'g'),
            FALSE,
            NULL,
            NULL,
            now(),
            now()
        FROM book_editions be
        JOIN editions e ON e.id = be.generic_edition_id
        WHERE e.upc IS NOT NULL AND trim(e.upc) <> ''
        ON CONFLICT (edition_id, identifier_type, normalized_value) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO book_identifiers (
            id,
            edition_id,
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
            be.id,
            'provider_item_id',
            ipl.provider_item_id,
            regexp_replace(lower(ipl.provider_item_id), '[^a-z0-9]+', '', 'g'),
            FALSE,
            ipl.provider,
            NULL,
            now(),
            now()
        FROM book_editions be
        JOIN editions e ON e.id = be.generic_edition_id
        JOIN item_provider_links ipl ON ipl.item_id = e.item_id
        WHERE ipl.provider_item_id IS NOT NULL AND trim(ipl.provider_item_id) <> ''
        ON CONFLICT (edition_id, identifier_type, normalized_value) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO book_series_memberships (
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
            bw.id,
            v.series_id,
            MIN(
                CASE
                    WHEN i.item_number ~ '^\\d+(\\.\\d+)?$' THEN i.item_number::float
                    ELSE NULL
                END
            ) AS sequence,
            MIN(NULLIF(trim(i.item_number), '')) AS display_number,
            NULL,
            now(),
            now()
        FROM book_works bw
        JOIN items i ON i.id = bw.generic_item_id
        JOIN volumes v ON v.id = i.volume_id
        WHERE i.kind = 'book'
        GROUP BY bw.id, v.series_id
        ON CONFLICT (work_id, series_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_book_series_memberships_series_sequence", table_name="book_series_memberships")
    op.drop_index("ix_book_series_memberships_series_id", table_name="book_series_memberships")
    op.drop_index("ix_book_series_memberships_work_id", table_name="book_series_memberships")
    op.drop_table("book_series_memberships")

    op.drop_index("ix_book_identifiers_type_value", table_name="book_identifiers")
    op.drop_index("ix_book_identifiers_source_provider", table_name="book_identifiers")
    op.drop_index("ix_book_identifiers_identifier_type", table_name="book_identifiers")
    op.drop_index("ix_book_identifiers_edition_id", table_name="book_identifiers")
    op.drop_table("book_identifiers")

    op.drop_index("ix_book_contributions_edition_role_sequence", table_name="book_contributions")
    op.drop_index("ix_book_contributions_work_role_sequence", table_name="book_contributions")
    op.drop_index("ix_book_contributions_role", table_name="book_contributions")
    op.drop_index("ix_book_contributions_person_id", table_name="book_contributions")
    op.drop_index("ix_book_contributions_edition_id", table_name="book_contributions")
    op.drop_index("ix_book_contributions_work_id", table_name="book_contributions")
    op.drop_table("book_contributions")

    op.drop_index("ix_book_printings_printing_number", table_name="book_printings")
    op.drop_index("ix_book_printings_edition_id", table_name="book_printings")
    op.drop_table("book_printings")

    op.drop_index("ix_book_editions_work_publication", table_name="book_editions")
    op.drop_index("ix_book_editions_release_status", table_name="book_editions")
    op.drop_index("ix_book_editions_age_rating", table_name="book_editions")
    op.drop_index("ix_book_editions_region", table_name="book_editions")
    op.drop_index("ix_book_editions_language", table_name="book_editions")
    op.drop_index("ix_book_editions_imprint", table_name="book_editions")
    op.drop_index("ix_book_editions_publisher", table_name="book_editions")
    op.drop_index("ix_book_editions_publication_date", table_name="book_editions")
    op.drop_index("ix_book_editions_binding", table_name="book_editions")
    op.drop_index("ix_book_editions_format", table_name="book_editions")
    op.drop_index("ix_book_editions_generic_edition_id", table_name="book_editions")
    op.drop_index("ix_book_editions_work_id", table_name="book_editions")
    op.drop_table("book_editions")

    op.drop_index("ix_book_works_first_publication_date", table_name="book_works")
    op.drop_index("ix_book_works_original_publication_date", table_name="book_works")
    op.drop_index("ix_book_works_original_language", table_name="book_works")
    op.drop_index("ix_book_works_sort_title", table_name="book_works")
    op.drop_index("ix_book_works_title", table_name="book_works")
    op.drop_index("ix_book_works_generic_item_id", table_name="book_works")
    op.drop_table("book_works")
