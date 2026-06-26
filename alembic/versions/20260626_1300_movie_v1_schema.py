"""Movie v1 schema - physical releases model.

Revision ID: 20260626_1300_movie_v1_schema
Revises: 20260626_1200_music_v1_schema
Create Date: 2026-06-26 19:05:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260626_1300_movie_v1_schema"
down_revision: str | None = "20260626_1200_music_v1_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Movie v1 schema tables."""
    op.create_table(
        "movie_works",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("sort_title", sa.String(), nullable=True),
        sa.Column("subtitle", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_language", sa.String(length=2), nullable=True),
        sa.Column("original_title", sa.String(), nullable=True),
        sa.Column("original_release_date", sa.Date(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("budget_usd", sa.BigInteger(), nullable=True),
        sa.Column("revenue_usd", sa.BigInteger(), nullable=True),
        sa.Column("audience_rating", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("rating_count", sa.Integer(), nullable=True),
        sa.Column("poster_image_url", sa.String(), nullable=True),
        sa.Column("poster_image_key", sa.String(), nullable=True),
        sa.Column("backdrop_image_url", sa.String(), nullable=True),
        sa.Column("backdrop_image_key", sa.String(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_movie_works_created_at", "movie_works", ["created_at"])

    op.create_table(
        "movie_releases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("work_id", sa.UUID(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("region_code", sa.String(length=2), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("release_type", sa.String(), nullable=True),
        sa.Column("certification", sa.String(), nullable=True),
        sa.Column("publisher", sa.String(), nullable=True),
        sa.Column("sku", sa.String(), nullable=True),
        sa.Column("barcode", sa.String(), nullable=True),
        sa.Column("media_count", sa.Integer(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("language_audio", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("language_subtitles", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("cover_image_url", sa.String(), nullable=True),
        sa.Column("cover_image_key", sa.String(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["work_id"], ["movie_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "region_code", "format"),
    )
    op.create_index("ix_movie_releases_work_id", "movie_releases", ["work_id"])
    op.create_index("ix_movie_releases_barcode", "movie_releases", ["barcode"])
    op.create_index("ix_movie_releases_created_at", "movie_releases", ["created_at"])

    op.create_table(
        "movie_release_media",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("media_number", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("aspect_ratio", sa.String(), nullable=True),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("nr_layers", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["release_id"], ["movie_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "media_number"),
    )
    op.create_index("ix_movie_release_media_release_id", "movie_release_media", ["release_id"])

    op.create_table(
        "movie_work_contributions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("work_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("character_name", sa.String(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["movie_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "person_id", "role"),
    )
    op.create_index("ix_movie_work_contributions_work_id", "movie_work_contributions", ["work_id"])
    op.create_index("ix_movie_work_contributions_role", "movie_work_contributions", ["work_id", "role"])

    op.create_table(
        "movie_work_identifiers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("work_id", sa.UUID(), nullable=False),
        sa.Column("identifier_type", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("normalized_value", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source_provider", sa.String(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["work_id"], ["movie_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "identifier_type", "value"),
    )
    op.create_index("ix_movie_work_identifiers_work_id", "movie_work_identifiers", ["work_id"])
    op.create_index("ix_movie_work_identifiers_type_value", "movie_work_identifiers", ["identifier_type", "value"])


def downgrade() -> None:
    """Drop Movie v1 schema tables."""
    op.drop_table("movie_work_identifiers")
    op.drop_table("movie_work_contributions")
    op.drop_table("movie_release_media")
    op.drop_table("movie_releases")
    op.drop_table("movie_works")
