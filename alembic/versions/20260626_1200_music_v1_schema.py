"""Music v1 schema - physical releases model.

Revision ID: 20260626_1200_music_v1_schema
Revises: 20260626_1100_tv_v1_hard_cutover
Create Date: 2026-06-26 19:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260626_1200_music_v1_schema"
down_revision: str | None = "20260626_1100_tv_v1_hard_cutover"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Music v1 schema tables."""
    op.create_table(
        "music_releases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("sort_title", sa.String(), nullable=True),
        sa.Column("release_type", sa.String(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("media_count", sa.Integer(), nullable=True),
        sa.Column("track_count", sa.Integer(), nullable=True),
        sa.Column("cover_image_url", sa.String(), nullable=True),
        sa.Column("cover_image_key", sa.String(), nullable=True),
        sa.Column("publisher", sa.String(), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("language", sa.String(length=2), nullable=True),
        sa.Column("barcode", sa.String(), nullable=True),
        sa.Column("catalog_number", sa.String(), nullable=True),
        sa.Column("audience_rating", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("rating_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_music_releases_barcode", "music_releases", ["barcode"])
    op.create_index("ix_music_releases_created_at", "music_releases", ["created_at"])

    op.create_table(
        "music_media",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("media_number", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("track_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["release_id"], ["music_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "media_number"),
    )
    op.create_index("ix_music_media_release_id", "music_media", ["release_id"])

    op.create_table(
        "music_tracks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("media_id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["media_id"], ["music_media.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["music_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_id", "position"),
    )
    op.create_index("ix_music_tracks_release_id", "music_tracks", ["release_id"])

    op.create_table(
        "music_release_contributions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["music_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "person_id", "role"),
    )
    op.create_index("ix_music_release_contributions_release_id", "music_release_contributions", ["release_id"])
    op.create_index("ix_music_release_contributions_role", "music_release_contributions", ["release_id", "role"])

    op.create_table(
        "music_release_identifiers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("identifier_type", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("normalized_value", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source_provider", sa.String(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["release_id"], ["music_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "identifier_type", "value"),
    )
    op.create_index("ix_music_release_identifiers_release_id", "music_release_identifiers", ["release_id"])
    op.create_index("ix_music_release_identifiers_type_value", "music_release_identifiers", ["identifier_type", "value"])


def downgrade() -> None:
    """Drop Music v1 schema tables."""
    op.drop_table("music_release_identifiers")
    op.drop_table("music_release_contributions")
    op.drop_table("music_tracks")
    op.drop_table("music_media")
    op.drop_table("music_releases")
