"""Add game and boardgame v1 schema.

Revision ID: 20260627_0300
Revises: 20260627_0200
Create Date: 2026-06-27 03:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260627_0300"
down_revision: str | None = "20260627_0200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "game_works",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_title", sa.String(length=255), nullable=True),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("original_language", sa.String(length=16), nullable=True),
        sa.Column("age_rating", sa.String(length=64), nullable=True),
        sa.Column("audience_rating", sa.String(length=64), nullable=True),
        sa.Column("cover_image_url", sa.String(length=2048), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_game_works_title", "game_works", ["title"], unique=False)
    op.create_index("ix_game_works_release_date", "game_works", ["release_date"], unique=False)
    op.create_index("ix_game_works_sort_title", "game_works", ["sort_title"], unique=False)

    op.create_table(
        "game_releases",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("release_title", sa.String(length=255), nullable=True),
        sa.Column("platform", sa.String(length=128), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("region_code", sa.String(length=32), nullable=True),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("catalog_number", sa.String(length=100), nullable=True),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("release_status", sa.String(length=64), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("cover_image_url", sa.String(length=2048), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["work_id"], ["game_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_game_releases_work_id", "game_releases", ["work_id"], unique=False)
    op.create_index("ix_game_releases_work_platform", "game_releases", ["work_id", "platform"], unique=False)
    op.create_index("ix_game_releases_barcode", "game_releases", ["barcode"], unique=False)
    op.create_index("ix_game_releases_platform", "game_releases", ["platform"], unique=False)
    op.create_index("ix_game_releases_release_date", "game_releases", ["release_date"], unique=False)

    op.create_table(
        "boardgame_works",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_title", sa.String(length=255), nullable=True),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("original_language", sa.String(length=16), nullable=True),
        sa.Column("age_rating", sa.String(length=64), nullable=True),
        sa.Column("audience_rating", sa.String(length=64), nullable=True),
        sa.Column("cover_image_url", sa.String(length=2048), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_boardgame_works_title", "boardgame_works", ["title"], unique=False)
    op.create_index("ix_boardgame_works_release_date", "boardgame_works", ["release_date"], unique=False)
    op.create_index("ix_boardgame_works_sort_title", "boardgame_works", ["sort_title"], unique=False)

    op.create_table(
        "boardgame_editions",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edition_title", sa.String(length=255), nullable=True),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("catalog_number", sa.String(length=100), nullable=True),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("release_status", sa.String(length=64), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("country", sa.String(length=32), nullable=True),
        sa.Column("age_rating", sa.String(length=64), nullable=True),
        sa.Column("audience_rating", sa.String(length=64), nullable=True),
        sa.Column("min_players", sa.Integer(), nullable=True),
        sa.Column("max_players", sa.Integer(), nullable=True),
        sa.Column("playing_time_minutes", sa.Integer(), nullable=True),
        sa.Column("min_age", sa.Integer(), nullable=True),
        sa.Column("cover_image_url", sa.String(length=2048), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["work_id"], ["boardgame_works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_boardgame_editions_work_id", "boardgame_editions", ["work_id"], unique=False)
    op.create_index(
        "ix_boardgame_editions_work_release",
        "boardgame_editions",
        ["work_id", "release_date"],
        unique=False,
    )
    op.create_index("ix_boardgame_editions_barcode", "boardgame_editions", ["barcode"], unique=False)
    op.create_index("ix_boardgame_editions_publisher", "boardgame_editions", ["publisher"], unique=False)
    op.create_index("ix_boardgame_editions_release_date", "boardgame_editions", ["release_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_boardgame_editions_release_date", table_name="boardgame_editions")
    op.drop_index("ix_boardgame_editions_publisher", table_name="boardgame_editions")
    op.drop_index("ix_boardgame_editions_barcode", table_name="boardgame_editions")
    op.drop_index("ix_boardgame_editions_work_release", table_name="boardgame_editions")
    op.drop_index("ix_boardgame_editions_work_id", table_name="boardgame_editions")
    op.drop_table("boardgame_editions")

    op.drop_index("ix_boardgame_works_sort_title", table_name="boardgame_works")
    op.drop_index("ix_boardgame_works_release_date", table_name="boardgame_works")
    op.drop_index("ix_boardgame_works_title", table_name="boardgame_works")
    op.drop_table("boardgame_works")

    op.drop_index("ix_game_releases_release_date", table_name="game_releases")
    op.drop_index("ix_game_releases_platform", table_name="game_releases")
    op.drop_index("ix_game_releases_barcode", table_name="game_releases")
    op.drop_index("ix_game_releases_work_platform", table_name="game_releases")
    op.drop_index("ix_game_releases_work_id", table_name="game_releases")
    op.drop_table("game_releases")

    op.drop_index("ix_game_works_sort_title", table_name="game_works")
    op.drop_index("ix_game_works_release_date", table_name="game_works")
    op.drop_index("ix_game_works_title", table_name="game_works")
    op.drop_table("game_works")
