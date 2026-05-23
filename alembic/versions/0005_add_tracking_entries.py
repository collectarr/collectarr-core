"""add tracking entries

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-23 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tracking_entries",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("owned_item_id", sa.UUID(), nullable=True),
        sa.Column("edition_id", sa.UUID(), nullable=True),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_current", sa.Integer(), nullable=True),
        sa.Column("progress_total", sa.Integer(), nullable=True),
        sa.Column("times_completed", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("season_number", sa.Integer(), nullable=True),
        sa.Column("episode_number", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["edition_id"], ["editions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["variants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tracking_entries_deleted_at"), "tracking_entries", ["deleted_at"])
    op.create_index(op.f("ix_tracking_entries_edition_id"), "tracking_entries", ["edition_id"])
    op.create_index(op.f("ix_tracking_entries_item_id"), "tracking_entries", ["item_id"])
    op.create_index(op.f("ix_tracking_entries_owned_item_id"), "tracking_entries", ["owned_item_id"])
    op.create_index(op.f("ix_tracking_entries_source_type"), "tracking_entries", ["source_type"])
    op.create_index(op.f("ix_tracking_entries_status"), "tracking_entries", ["status"])
    op.create_index(op.f("ix_tracking_entries_updated_at"), "tracking_entries", ["updated_at"])
    op.create_index(op.f("ix_tracking_entries_user_id"), "tracking_entries", ["user_id"])
    op.create_index(op.f("ix_tracking_entries_variant_id"), "tracking_entries", ["variant_id"])
    op.create_index("ix_tracking_entries_owned_item", "tracking_entries", ["owned_item_id"])
    op.create_index("ix_tracking_entries_updated", "tracking_entries", ["updated_at"])
    op.create_index("ix_tracking_entries_user_item", "tracking_entries", ["user_id", "item_id"])
    op.create_index("ix_tracking_entries_user_status", "tracking_entries", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_tracking_entries_user_status", table_name="tracking_entries")
    op.drop_index("ix_tracking_entries_user_item", table_name="tracking_entries")
    op.drop_index("ix_tracking_entries_updated", table_name="tracking_entries")
    op.drop_index("ix_tracking_entries_owned_item", table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_variant_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_user_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_updated_at"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_status"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_source_type"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_owned_item_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_item_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_edition_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_deleted_at"), table_name="tracking_entries")
    op.drop_table("tracking_entries")