"""Add admin release mapping rules table.

Revision ID: 20260604_0001
Revises: 20260530_0001
Create Date: 2026-06-04 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260604_0001"
down_revision: str | None = "20260530_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_release_media_mapping_rules",
        sa.Column("provider", sa.Enum(name="external_provider", create_type=False), nullable=True),
        sa.Column("release_type", sa.String(length=64), nullable=False),
        sa.Column("target_kind", sa.Enum(name="item_kind", create_type=False), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_release_media_mapping_rules_provider",
        "admin_release_media_mapping_rules",
        ["provider"],
    )
    op.create_index(
        "ix_admin_release_media_mapping_rules_release_type",
        "admin_release_media_mapping_rules",
        ["release_type"],
    )
    op.create_index(
        "ix_admin_release_media_mapping_rules_target_kind",
        "admin_release_media_mapping_rules",
        ["target_kind"],
    )
    op.create_index(
        "ix_admin_release_media_mapping_rules_is_active",
        "admin_release_media_mapping_rules",
        ["is_active"],
    )
    op.create_index(
        "ix_admin_release_media_mapping_rules_lookup",
        "admin_release_media_mapping_rules",
        ["release_type", "provider", "is_active", "priority"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_release_media_mapping_rules_lookup",
        table_name="admin_release_media_mapping_rules",
    )
    op.drop_index(
        "ix_admin_release_media_mapping_rules_is_active",
        table_name="admin_release_media_mapping_rules",
    )
    op.drop_index(
        "ix_admin_release_media_mapping_rules_target_kind",
        table_name="admin_release_media_mapping_rules",
    )
    op.drop_index(
        "ix_admin_release_media_mapping_rules_release_type",
        table_name="admin_release_media_mapping_rules",
    )
    op.drop_index(
        "ix_admin_release_media_mapping_rules_provider",
        table_name="admin_release_media_mapping_rules",
    )
    op.drop_table("admin_release_media_mapping_rules")
