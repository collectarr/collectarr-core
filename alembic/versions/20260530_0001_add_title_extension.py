"""Add title_extension column to items table.

Revision ID: 20260530_0001
Revises: 20260529_0003
Create Date: 2026-05-30 00:00:01
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260530_0001"
down_revision: str | None = "20260529_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS title_extension VARCHAR(255)")


def downgrade() -> None:
    op.drop_column("items", "title_extension")
