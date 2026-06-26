"""TV v1 schema - physical releases model.

Revision ID: 20260626_1000_tv_v1_schema
Revises: 20260625_1900_comics_v1_hard_cutover
Create Date: 2026-06-26 18:50:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260626_1000_tv_v1_schema"
down_revision: str | None = "20260625_1900_comics_v1_hard_cutover"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create TV v1 schema tables."""
    op.create_table(
        "tv_releases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("sort_title", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("media_count", sa.Integer(), nullable=True),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("region_code", sa.String(length=2), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("publisher", sa.String(), nullable=True),
        sa.Column("sku", sa.String(), nullable=True),
        sa.Column("case_type", sa.String(), nullable=True),
        sa.Column("episode_count", sa.Integer(), nullable=True),
        sa.Column("season_count", sa.Integer(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("language_audio", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("language_subtitles", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("content_rating", sa.String(), nullable=True),
        sa.Column("cover_image_url", sa.String(), nullable=True),
        sa.Column("cover_image_key", sa.String(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tv_releases_sort_title", "tv_releases", ["sort_title"], unique=False)
    op.create_index("idx_tv_releases_sku", "tv_releases", ["sku"], unique=False)

    op.create_table(
        "tv_release_media",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("media_number", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("episode_count", sa.Integer(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("region_code", sa.String(length=2), nullable=True),
        sa.Column("encoding", sa.String(), nullable=True),
        sa.Column("aspect_ratio", sa.String(), nullable=True),
        sa.Column("frame_rate", sa.String(), nullable=True),
        sa.Column("bit_depth", sa.String(), nullable=True),
        sa.Column("resolution", sa.String(), nullable=True),
        sa.Column("hdr_format", sa.String(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["release_id"], ["tv_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "media_number", name="unique_tv_release_media"),
    )
    op.create_index("idx_tv_release_media_release_id", "tv_release_media", ["release_id"], unique=False)

    op.create_table(
        "tv_episodes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("media_id", sa.UUID(), nullable=False),
        sa.Column("series_title", sa.String(), nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("original_air_date", sa.Date(), nullable=True),
        sa.Column("still_url", sa.String(), nullable=True),
        sa.Column("still_key", sa.String(), nullable=True),
        sa.Column("audio_tracks", postgresql.JSONB(), nullable=True),
        sa.Column("subtitle_tracks", postgresql.JSONB(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["release_id"], ["tv_releases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_id"], ["tv_release_media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "season_number", "episode_number", name="unique_tv_episode"),
    )
    op.create_index("idx_tv_episodes_release_id", "tv_episodes", ["release_id"], unique=False)
    op.create_index("idx_tv_episodes_media_id", "tv_episodes", ["media_id"], unique=False)

    op.create_table(
        "tv_release_contributions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("character_name", sa.String(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["release_id"], ["tv_releases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "person_id", "role", name="unique_tv_release_contribution"),
    )
    op.create_index("idx_tv_release_contributions_release_id", "tv_release_contributions", ["release_id"], unique=False)
    op.create_index("idx_tv_release_contributions_person_id", "tv_release_contributions", ["person_id"], unique=False)
    op.create_index("idx_tv_release_contributions_role", "tv_release_contributions", ["release_id", "role"], unique=False)

    op.create_table(
        "tv_release_identifiers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("identifier_type", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("normalized_value", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source_provider", sa.String(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["release_id"], ["tv_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_id", "identifier_type", "value", name="unique_tv_release_identifier"),
    )
    op.create_index("idx_tv_release_identifiers_release_id", "tv_release_identifiers", ["release_id"], unique=False)
    op.create_index("idx_tv_release_identifiers_type_value", "tv_release_identifiers", ["identifier_type", "value"], unique=False)


def downgrade() -> None:
    """Drop TV v1 schema tables."""
    op.drop_index("idx_tv_release_identifiers_type_value", table_name="tv_release_identifiers")
    op.drop_index("idx_tv_release_identifiers_release_id", table_name="tv_release_identifiers")
    op.drop_table("tv_release_identifiers")
    op.drop_index("idx_tv_release_contributions_role", table_name="tv_release_contributions")
    op.drop_index("idx_tv_release_contributions_person_id", table_name="tv_release_contributions")
    op.drop_index("idx_tv_release_contributions_release_id", table_name="tv_release_contributions")
    op.drop_table("tv_release_contributions")
    op.drop_index("idx_tv_episodes_media_id", table_name="tv_episodes")
    op.drop_index("idx_tv_episodes_release_id", table_name="tv_episodes")
    op.drop_table("tv_episodes")
    op.drop_index("idx_tv_release_media_release_id", table_name="tv_release_media")
    op.drop_table("tv_release_media")
    op.drop_index("idx_tv_releases_sku", table_name="tv_releases")
    op.drop_index("idx_tv_releases_sort_title", table_name="tv_releases")
    op.drop_table("tv_releases")
