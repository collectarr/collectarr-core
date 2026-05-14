"""add admin audit logs

Revision ID: 202605150001
Revises: 202605140003
Create Date: 2026-05-15 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605150001"
down_revision: str | None = "202605140003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_audit_logs_action_created",
        "admin_audit_logs",
        ["action", "created_at"],
    )
    op.create_index(
        "ix_admin_audit_logs_entity",
        "admin_audit_logs",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        op.f("ix_admin_audit_logs_action"),
        "admin_audit_logs",
        ["action"],
    )
    op.create_index(
        op.f("ix_admin_audit_logs_actor_email"),
        "admin_audit_logs",
        ["actor_email"],
    )
    op.create_index(
        op.f("ix_admin_audit_logs_actor_user_id"),
        "admin_audit_logs",
        ["actor_user_id"],
    )
    op.create_index(
        op.f("ix_admin_audit_logs_entity_id"),
        "admin_audit_logs",
        ["entity_id"],
    )
    op.create_index(
        op.f("ix_admin_audit_logs_entity_type"),
        "admin_audit_logs",
        ["entity_type"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_audit_logs_entity_type"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_entity_id"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_actor_user_id"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_actor_email"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_action"), table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_entity", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action_created", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
