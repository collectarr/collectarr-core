"""add image cache entries

Revision ID: 202605140002
Revises: 202605140001
Create Date: 2026-05-14 16:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202605140002"
down_revision: str | None = "202605140001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "image_cache_entries",
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_item_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("public_url", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("access_count", sa.Integer(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_image_cache_object_key"),
    )
    op.create_index(
        "ix_image_cache_last_accessed",
        "image_cache_entries",
        ["last_accessed_at"],
    )
    op.create_index(
        "ix_image_cache_provider_source",
        "image_cache_entries",
        ["provider", "source_url"],
    )
    op.create_index(
        op.f("ix_image_cache_entries_content_hash"),
        "image_cache_entries",
        ["content_hash"],
    )
    op.create_index(
        op.f("ix_image_cache_entries_provider"),
        "image_cache_entries",
        ["provider"],
    )
    op.create_index(
        op.f("ix_image_cache_entries_provider_item_id"),
        "image_cache_entries",
        ["provider_item_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_image_cache_entries_provider_item_id"), table_name="image_cache_entries")
    op.drop_index(op.f("ix_image_cache_entries_provider"), table_name="image_cache_entries")
    op.drop_index(op.f("ix_image_cache_entries_content_hash"), table_name="image_cache_entries")
    op.drop_index("ix_image_cache_provider_source", table_name="image_cache_entries")
    op.drop_index("ix_image_cache_last_accessed", table_name="image_cache_entries")
    op.drop_table("image_cache_entries")
