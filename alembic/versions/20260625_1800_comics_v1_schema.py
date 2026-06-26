"""Add comics v1 relational work/issue module.

Revision ID: 20260625_1800
Revises: 20260625_1700
Create Date: 2026-06-25 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_1800"
down_revision: str | None = "20260625_1700"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comic_works",
        sa.Column("volume_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_title", sa.String(length=255), nullable=True),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_language", sa.String(length=16), nullable=True),
        sa.Column("first_publication_date", sa.Date(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["volume_id"], ["volumes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("volume_id", name="uq_comic_works_volume_id"),
    )
    op.create_index("ix_comic_works_volume_id", "comic_works", ["volume_id"], unique=False)
    op.create_index("ix_comic_works_title", "comic_works", ["title"], unique=False)
    op.create_index("ix_comic_works_sort_title", "comic_works", ["sort_title"], unique=False)
    op.create_index("ix_comic_works_original_language", "comic_works", ["original_language"], unique=False)
    op.create_index(
        "ix_comic_works_first_publication_date",
        "comic_works",
        ["first_publication_date"],
        unique=False,
    )

    op.create_table(
        "comic_issues",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generic_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issue_number", sa.String(length=64), nullable=True),
        sa.Column("display_title", sa.String(length=255), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("imprint", sa.String(length=255), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("cover_price_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("release_status", sa.String(length=64), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["generic_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["work_id"], ["comic_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_item_id", name="uq_comic_issues_generic_item_id"),
    )
    op.create_index("ix_comic_issues_work_id", "comic_issues", ["work_id"], unique=False)
    op.create_index("ix_comic_issues_generic_item_id", "comic_issues", ["generic_item_id"], unique=False)
    op.create_index("ix_comic_issues_issue_number", "comic_issues", ["issue_number"], unique=False)
    op.create_index("ix_comic_issues_publication_date", "comic_issues", ["publication_date"], unique=False)
    op.create_index("ix_comic_issues_release_date", "comic_issues", ["release_date"], unique=False)
    op.create_index("ix_comic_issues_publisher", "comic_issues", ["publisher"], unique=False)
    op.create_index("ix_comic_issues_imprint", "comic_issues", ["imprint"], unique=False)
    op.create_index("ix_comic_issues_language", "comic_issues", ["language"], unique=False)
    op.create_index("ix_comic_issues_region", "comic_issues", ["region"], unique=False)
    op.create_index("ix_comic_issues_release_status", "comic_issues", ["release_status"], unique=False)
    op.create_index(
        "ix_comic_issues_work_issue_number",
        "comic_issues",
        ["work_id", "issue_number"],
        unique=False,
    )
    op.create_index(
        "ix_comic_issues_work_publication",
        "comic_issues",
        ["work_id", "publication_date"],
        unique=False,
    )

    op.create_table(
        "comic_contributions",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((work_id IS NOT NULL AND issue_id IS NULL) OR (work_id IS NULL AND issue_id IS NOT NULL))",
            name="ck_comic_contributions_work_xor_issue",
        ),
        sa.ForeignKeyConstraint(["issue_id"], ["comic_issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["comic_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comic_contributions_work_id", "comic_contributions", ["work_id"], unique=False)
    op.create_index("ix_comic_contributions_issue_id", "comic_contributions", ["issue_id"], unique=False)
    op.create_index("ix_comic_contributions_person_id", "comic_contributions", ["person_id"], unique=False)
    op.create_index("ix_comic_contributions_role", "comic_contributions", ["role"], unique=False)
    op.create_index(
        "ix_comic_contributions_work_role_sequence",
        "comic_contributions",
        ["work_id", "role", "sequence"],
        unique=False,
    )
    op.create_index(
        "ix_comic_contributions_issue_role_sequence",
        "comic_contributions",
        ["issue_id", "role", "sequence"],
        unique=False,
    )

    op.create_table(
        "comic_identifiers",
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["issue_id"], ["comic_issues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "issue_id",
            "identifier_type",
            "normalized_value",
            name="uq_comic_identifiers_issue_type_normalized",
        ),
    )
    op.create_index("ix_comic_identifiers_issue_id", "comic_identifiers", ["issue_id"], unique=False)
    op.create_index("ix_comic_identifiers_identifier_type", "comic_identifiers", ["identifier_type"], unique=False)
    op.create_index("ix_comic_identifiers_source_provider", "comic_identifiers", ["source_provider"], unique=False)
    op.create_index(
        "ix_comic_identifiers_type_value",
        "comic_identifiers",
        ["identifier_type", "normalized_value"],
        unique=False,
    )

    op.create_table(
        "comic_story_arc_memberships",
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_arc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["comic_issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_arc_id"], ["story_arcs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issue_id", "story_arc_id", name="uq_comic_story_arc_memberships_issue_arc"),
    )
    op.create_index("ix_comic_story_arc_memberships_issue_id", "comic_story_arc_memberships", ["issue_id"], unique=False)
    op.create_index("ix_comic_story_arc_memberships_story_arc_id", "comic_story_arc_memberships", ["story_arc_id"], unique=False)
    op.create_index(
        "ix_comic_story_arc_memberships_issue_ordinal",
        "comic_story_arc_memberships",
        ["issue_id", "ordinal"],
        unique=False,
    )

    op.create_table(
        "comic_character_appearances",
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issue_id"], ["comic_issues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "issue_id",
            "character_id",
            "role",
            name="uq_comic_character_appearances_issue_character_role",
        ),
    )
    op.create_index("ix_comic_character_appearances_issue_id", "comic_character_appearances", ["issue_id"], unique=False)
    op.create_index("ix_comic_character_appearances_character_id", "comic_character_appearances", ["character_id"], unique=False)
    op.create_index("ix_comic_character_appearances_role", "comic_character_appearances", ["role"], unique=False)
    op.create_index(
        "ix_comic_character_appearances_issue_role",
        "comic_character_appearances",
        ["issue_id", "role"],
        unique=False,
    )

    op.create_table(
        "comic_series_memberships",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Float(), nullable=True),
        sa.Column("display_number", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["comic_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "series_id", name="uq_comic_series_memberships_work_series"),
    )
    op.create_index("ix_comic_series_memberships_work_id", "comic_series_memberships", ["work_id"], unique=False)
    op.create_index("ix_comic_series_memberships_series_id", "comic_series_memberships", ["series_id"], unique=False)
    op.create_index(
        "ix_comic_series_memberships_series_sequence",
        "comic_series_memberships",
        ["series_id", "sequence"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO comic_works (
            id,
            volume_id,
            title,
            sort_title,
            subtitle,
            description,
            original_language,
            first_publication_date,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            v.id,
            COALESCE(NULLIF(trim(s.title), ''), NULLIF(trim(v.name), ''), 'Unknown Comic Work'),
            lower(COALESCE(NULLIF(trim(s.title), ''), NULLIF(trim(v.name), ''), 'Unknown Comic Work')),
            NULL,
            NULL,
            NULL,
            NULL,
            jsonb_build_object('backfilled_from_volume', v.id::text),
            now(),
            now()
        FROM volumes v
        JOIN series s ON s.id = v.series_id
        WHERE s.kind = 'comic'
          AND EXISTS (
              SELECT 1
              FROM items i
              WHERE i.volume_id = v.id
                AND i.kind = 'comic'
          )
          AND NOT EXISTS (
              SELECT 1 FROM comic_works cw WHERE cw.volume_id = v.id
          )
        """
    )

    op.execute(
        """
        INSERT INTO comic_issues (
            id,
            work_id,
            generic_item_id,
            issue_number,
            display_title,
            publication_date,
            release_date,
            publisher,
            imprint,
            language,
            region,
            page_count,
            cover_price_cents,
            currency,
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
            cw.id,
            i.id,
            NULLIF(trim(i.item_number), ''),
            NULLIF(trim(COALESCE(e.title, i.title)), ''),
            e.release_date,
            e.release_date,
            e.publisher,
            e.imprint,
            e.language,
            e.region,
            i.page_count,
            primary_variant.cover_price_cents,
            primary_variant.currency,
            e.release_status,
            primary_variant.cover_image_url,
            primary_variant.cover_image_key,
            COALESCE(i.plot_description, i.plot_summary, i.synopsis),
            jsonb_build_object('backfilled_from_item', i.id::text),
            now(),
            now()
        FROM items i
        JOIN comic_works cw ON cw.volume_id = i.volume_id
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
        WHERE i.kind = 'comic'
          AND NOT EXISTS (
              SELECT 1 FROM comic_issues ci WHERE ci.generic_item_id = i.id
          )
        """
    )

    op.execute(
        """
        UPDATE comic_works cw
        SET first_publication_date = src.first_publication_date
        FROM (
            SELECT ci.work_id, MIN(ci.publication_date) AS first_publication_date
            FROM comic_issues ci
            GROUP BY ci.work_id
        ) src
        WHERE src.work_id = cw.id
        """
    )

    op.execute(
        """
        INSERT INTO comic_contributions (
            id,
            work_id,
            issue_id,
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
            ci.id,
            ep.person_id,
            ep.role,
            row_number() OVER (
                PARTITION BY ci.id, ep.role
                ORDER BY ep.created_at ASC, ep.id ASC
            ),
            NULL,
            now(),
            now()
        FROM entity_persons ep
        JOIN comic_issues ci ON ci.generic_item_id = ep.entity_id
        WHERE ep.entity_type = 'item'
        """
    )

    op.execute(
        """
        INSERT INTO comic_story_arc_memberships (
            id,
            issue_id,
            story_arc_id,
            ordinal,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            ci.id,
            sai.story_arc_id,
            sai.ordinal,
            NULL,
            now(),
            now()
        FROM story_arc_items sai
        JOIN comic_issues ci ON ci.generic_item_id = sai.item_id
        ON CONFLICT (issue_id, story_arc_id) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO comic_character_appearances (
            id,
            issue_id,
            character_id,
            role,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            ci.id,
            ca.character_id,
            ca.role,
            NULL,
            now(),
            now()
        FROM character_appearances ca
        JOIN comic_issues ci ON ci.generic_item_id = ca.item_id
        ON CONFLICT (issue_id, character_id, role) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO comic_identifiers (
            id,
            issue_id,
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
            ci.id,
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
        FROM comic_issues ci
        JOIN items i ON i.id = ci.generic_item_id
        JOIN editions e ON e.item_id = i.id
        WHERE e.isbn IS NOT NULL AND trim(e.isbn) <> ''
        ON CONFLICT (issue_id, identifier_type, normalized_value) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO comic_identifiers (
            id,
            issue_id,
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
            ci.id,
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
        FROM comic_issues ci
        JOIN items i ON i.id = ci.generic_item_id
        JOIN editions e ON e.item_id = i.id
        JOIN variants v ON v.edition_id = e.id
        WHERE v.barcode IS NOT NULL AND trim(v.barcode) <> ''
        ON CONFLICT (issue_id, identifier_type, normalized_value) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO comic_identifiers (
            id,
            issue_id,
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
            ci.id,
            'provider_item_id',
            ipl.provider_item_id,
            regexp_replace(lower(ipl.provider_item_id), '[^a-z0-9]+', '', 'g'),
            FALSE,
            ipl.provider,
            NULL,
            now(),
            now()
        FROM comic_issues ci
        JOIN item_provider_links ipl ON ipl.item_id = ci.generic_item_id
        WHERE ipl.provider_item_id IS NOT NULL AND trim(ipl.provider_item_id) <> ''
        ON CONFLICT (issue_id, identifier_type, normalized_value) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO comic_series_memberships (
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
            cw.id,
            v.series_id,
            MIN(
                CASE
                    WHEN ci.issue_number ~ '^\\d+(\\.\\d+)?$' THEN ci.issue_number::float
                    ELSE NULL
                END
            ) AS sequence,
            MIN(NULLIF(trim(ci.issue_number), '')) AS display_number,
            NULL,
            now(),
            now()
        FROM comic_works cw
        JOIN volumes v ON v.id = cw.volume_id
        LEFT JOIN comic_issues ci ON ci.work_id = cw.id
        GROUP BY cw.id, v.series_id
        ON CONFLICT (work_id, series_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_comic_series_memberships_series_sequence", table_name="comic_series_memberships")
    op.drop_index("ix_comic_series_memberships_series_id", table_name="comic_series_memberships")
    op.drop_index("ix_comic_series_memberships_work_id", table_name="comic_series_memberships")
    op.drop_table("comic_series_memberships")

    op.drop_index("ix_comic_character_appearances_issue_role", table_name="comic_character_appearances")
    op.drop_index("ix_comic_character_appearances_role", table_name="comic_character_appearances")
    op.drop_index("ix_comic_character_appearances_character_id", table_name="comic_character_appearances")
    op.drop_index("ix_comic_character_appearances_issue_id", table_name="comic_character_appearances")
    op.drop_table("comic_character_appearances")

    op.drop_index("ix_comic_story_arc_memberships_issue_ordinal", table_name="comic_story_arc_memberships")
    op.drop_index("ix_comic_story_arc_memberships_story_arc_id", table_name="comic_story_arc_memberships")
    op.drop_index("ix_comic_story_arc_memberships_issue_id", table_name="comic_story_arc_memberships")
    op.drop_table("comic_story_arc_memberships")

    op.drop_index("ix_comic_identifiers_type_value", table_name="comic_identifiers")
    op.drop_index("ix_comic_identifiers_source_provider", table_name="comic_identifiers")
    op.drop_index("ix_comic_identifiers_identifier_type", table_name="comic_identifiers")
    op.drop_index("ix_comic_identifiers_issue_id", table_name="comic_identifiers")
    op.drop_table("comic_identifiers")

    op.drop_index("ix_comic_contributions_issue_role_sequence", table_name="comic_contributions")
    op.drop_index("ix_comic_contributions_work_role_sequence", table_name="comic_contributions")
    op.drop_index("ix_comic_contributions_role", table_name="comic_contributions")
    op.drop_index("ix_comic_contributions_person_id", table_name="comic_contributions")
    op.drop_index("ix_comic_contributions_issue_id", table_name="comic_contributions")
    op.drop_index("ix_comic_contributions_work_id", table_name="comic_contributions")
    op.drop_table("comic_contributions")

    op.drop_index("ix_comic_issues_work_publication", table_name="comic_issues")
    op.drop_index("ix_comic_issues_work_issue_number", table_name="comic_issues")
    op.drop_index("ix_comic_issues_release_status", table_name="comic_issues")
    op.drop_index("ix_comic_issues_region", table_name="comic_issues")
    op.drop_index("ix_comic_issues_language", table_name="comic_issues")
    op.drop_index("ix_comic_issues_imprint", table_name="comic_issues")
    op.drop_index("ix_comic_issues_publisher", table_name="comic_issues")
    op.drop_index("ix_comic_issues_release_date", table_name="comic_issues")
    op.drop_index("ix_comic_issues_publication_date", table_name="comic_issues")
    op.drop_index("ix_comic_issues_issue_number", table_name="comic_issues")
    op.drop_index("ix_comic_issues_generic_item_id", table_name="comic_issues")
    op.drop_index("ix_comic_issues_work_id", table_name="comic_issues")
    op.drop_table("comic_issues")

    op.drop_index("ix_comic_works_first_publication_date", table_name="comic_works")
    op.drop_index("ix_comic_works_original_language", table_name="comic_works")
    op.drop_index("ix_comic_works_sort_title", table_name="comic_works")
    op.drop_index("ix_comic_works_title", table_name="comic_works")
    op.drop_index("ix_comic_works_volume_id", table_name="comic_works")
    op.drop_table("comic_works")
