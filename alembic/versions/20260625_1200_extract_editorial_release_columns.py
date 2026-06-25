"""Extract editorial/release fields from metadata_json into typed columns.

Revision ID: 20260625_1200
Revises: 20260625_1100
Create Date: 2026-06-25 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260625_1200"
down_revision: str | None = "20260625_1150"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("original_title", sa.String(length=255), nullable=True))
    op.add_column("items", sa.Column("localized_title", sa.String(length=255), nullable=True))
    op.add_column("items", sa.Column("search_aliases", postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column("items", sa.Column("crossover", sa.String(length=255), nullable=True))
    op.add_column("items", sa.Column("plot_summary", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("plot_description", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("trailer_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("items", sa.Column("external_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.add_column("editions", sa.Column("physical_format", sa.String(length=64), nullable=True))
    op.add_column("editions", sa.Column("physical_format_label", sa.String(length=64), nullable=True))
    op.add_column("editions", sa.Column("physical_format_media_family", sa.String(length=64), nullable=True))
    op.add_column("editions", sa.Column("physical_format_variant_type", sa.String(length=64), nullable=True))
    op.create_index("ix_editions_physical_format", "editions", ["physical_format"], unique=False)

    op.add_column("variants", sa.Column("physical_format", sa.String(length=64), nullable=True))
    op.add_column("variants", sa.Column("physical_format_label", sa.String(length=64), nullable=True))
    op.add_column("variants", sa.Column("physical_format_media_family", sa.String(length=64), nullable=True))
    op.add_column("variants", sa.Column("physical_format_variant_type", sa.String(length=64), nullable=True))
    op.create_index("ix_variants_physical_format", "variants", ["physical_format"], unique=False)

    op.execute(
        """
        UPDATE items
        SET
            original_title = COALESCE(metadata_json->>'original_title', metadata_json #>> '{normalized,original_title}'),
            localized_title = COALESCE(metadata_json->>'localized_title', metadata_json #>> '{normalized,localized_title}'),
            search_aliases = (
                CASE
                    WHEN jsonb_typeof(COALESCE(metadata_json->'search_aliases', metadata_json #> '{normalized,search_aliases}')) = 'array'
                    THEN ARRAY(
                        SELECT jsonb_array_elements_text(
                            COALESCE(metadata_json->'search_aliases', metadata_json #> '{normalized,search_aliases}')
                        )
                    )
                    ELSE NULL
                END
            ),
            crossover = COALESCE(metadata_json->>'crossover', metadata_json #>> '{normalized,crossover}'),
            plot_summary = COALESCE(metadata_json->>'plot_summary', metadata_json #>> '{normalized,plot_summary}'),
            plot_description = COALESCE(metadata_json->>'plot_description', metadata_json #>> '{normalized,plot_description}'),
            trailer_urls = CASE
                WHEN jsonb_typeof(metadata_json->'trailer_urls') = 'array'
                THEN metadata_json->'trailer_urls'
                ELSE NULL
            END,
            external_links = CASE
                WHEN jsonb_typeof(metadata_json->'external_links') = 'array'
                THEN metadata_json->'external_links'
                ELSE NULL
            END
        WHERE metadata_json IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE editions
        SET
            physical_format = COALESCE(metadata_json #>> '{normalized,physical_format}', metadata_json->>'physical_format'),
            physical_format_label = COALESCE(metadata_json #>> '{normalized,physical_format_label}', metadata_json->>'physical_format_label'),
            physical_format_media_family = COALESCE(metadata_json #>> '{normalized,physical_format_media_family}', metadata_json->>'physical_format_media_family'),
            physical_format_variant_type = COALESCE(metadata_json #>> '{normalized,physical_format_variant_type}', metadata_json->>'physical_format_variant_type')
        WHERE metadata_json IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE variants
        SET
            physical_format = COALESCE(metadata_json #>> '{normalized,physical_format}', metadata_json->>'physical_format'),
            physical_format_label = COALESCE(metadata_json #>> '{normalized,physical_format_label}', metadata_json->>'physical_format_label'),
            physical_format_media_family = COALESCE(metadata_json #>> '{normalized,physical_format_media_family}', metadata_json->>'physical_format_media_family'),
            physical_format_variant_type = COALESCE(metadata_json #>> '{normalized,physical_format_variant_type}', metadata_json->>'physical_format_variant_type')
        WHERE metadata_json IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_variants_physical_format", table_name="variants")
    op.drop_column("variants", "physical_format_variant_type")
    op.drop_column("variants", "physical_format_media_family")
    op.drop_column("variants", "physical_format_label")
    op.drop_column("variants", "physical_format")

    op.drop_index("ix_editions_physical_format", table_name="editions")
    op.drop_column("editions", "physical_format_variant_type")
    op.drop_column("editions", "physical_format_media_family")
    op.drop_column("editions", "physical_format_label")
    op.drop_column("editions", "physical_format")

    op.drop_column("items", "external_links")
    op.drop_column("items", "trailer_urls")
    op.drop_column("items", "plot_description")
    op.drop_column("items", "plot_summary")
    op.drop_column("items", "crossover")
    op.drop_column("items", "search_aliases")
    op.drop_column("items", "localized_title")
    op.drop_column("items", "original_title")
