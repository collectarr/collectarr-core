"""add metadata proposals

Revision ID: 202605110003
Revises: 202605110002
Create Date: 2026-05-11 20:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605110003"
down_revision: str | None = "202605110002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    external_provider = postgresql.ENUM(
        "comicvine", "igdb", "tmdb", name="external_provider", create_type=False
    )
    op.create_table(
        "metadata_proposals",
        sa.Column("provider", external_provider, nullable=False),
        sa.Column("provider_item_id", sa.String(length=255), nullable=True),
        sa.Column("query", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_metadata_proposals_status_provider",
        "metadata_proposals",
        ["status", "provider"],
    )
    op.create_index(
        op.f("ix_metadata_proposals_provider"),
        "metadata_proposals",
        ["provider"],
    )
    op.create_index(
        op.f("ix_metadata_proposals_provider_item_id"),
        "metadata_proposals",
        ["provider_item_id"],
    )
    op.create_index(
        op.f("ix_metadata_proposals_status"),
        "metadata_proposals",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_metadata_proposals_status"), table_name="metadata_proposals")
    op.drop_index(op.f("ix_metadata_proposals_provider_item_id"), table_name="metadata_proposals")
    op.drop_index(op.f("ix_metadata_proposals_provider"), table_name="metadata_proposals")
    op.drop_index("ix_metadata_proposals_status_provider", table_name="metadata_proposals")
    op.drop_table("metadata_proposals")
