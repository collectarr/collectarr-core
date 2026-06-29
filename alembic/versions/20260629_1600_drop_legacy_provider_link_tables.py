"""Drop legacy provider link tables.

Revision ID: 20260629_1600
Revises: 20260627_0400
Create Date: 2026-06-29 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260629_1600"
down_revision: str | None = "20260627_0400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = (
    "item_provider_links",
    "series_provider_links",
    "volume_provider_links",
    "bundle_release_provider_links",
)


def upgrade() -> None:
    for table_name in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")


def downgrade() -> None:
    op.create_table(
        "item_provider_links",
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_item_id", sa.String(length=255), nullable=False),
        sa.Column("site_url", sa.String(length=1024), nullable=True),
        sa.Column("api_url", sa.String(length=1024), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_item_id", name="uq_item_provider_links_provider_item_id"),
    )
    op.create_index("ix_item_provider_links_item_id", "item_provider_links", ["item_id"], unique=False)
    op.create_index("ix_item_provider_links_provider", "item_provider_links", ["provider"], unique=False)

    op.create_table(
        "series_provider_links",
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_item_id", sa.String(length=255), nullable=False),
        sa.Column("site_url", sa.String(length=1024), nullable=True),
        sa.Column("api_url", sa.String(length=1024), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_item_id", name="uq_series_provider_links_provider_item_id"),
    )
    op.create_index("ix_series_provider_links_series_id", "series_provider_links", ["series_id"], unique=False)
    op.create_index("ix_series_provider_links_provider", "series_provider_links", ["provider"], unique=False)

    op.create_table(
        "volume_provider_links",
        sa.Column("volume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_item_id", sa.String(length=255), nullable=False),
        sa.Column("site_url", sa.String(length=1024), nullable=True),
        sa.Column("api_url", sa.String(length=1024), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["volume_id"], ["volumes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_item_id", name="uq_volume_provider_links_provider_item_id"),
    )
    op.create_index("ix_volume_provider_links_volume_id", "volume_provider_links", ["volume_id"], unique=False)
    op.create_index("ix_volume_provider_links_provider", "volume_provider_links", ["provider"], unique=False)

    op.create_table(
        "bundle_release_provider_links",
        sa.Column("bundle_release_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_item_id", sa.String(length=255), nullable=False),
        sa.Column("site_url", sa.String(length=1024), nullable=True),
        sa.Column("api_url", sa.String(length=1024), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bundle_release_id"], ["bundle_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_item_id", name="uq_bundle_release_provider_links_provider_item_id"),
    )
    op.create_index(
        "ix_bundle_release_provider_links_bundle_release_id",
        "bundle_release_provider_links",
        ["bundle_release_id"],
        unique=False,
    )
    op.create_index(
        "ix_bundle_release_provider_links_provider",
        "bundle_release_provider_links",
        ["provider"],
        unique=False,
    )
