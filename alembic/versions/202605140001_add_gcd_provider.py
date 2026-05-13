"""add gcd provider enum value

Revision ID: 202605140001
Revises: 202605110003
Create Date: 2026-05-14 00:01:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202605140001"
down_revision: str | None = "202605110003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE external_provider ADD VALUE IF NOT EXISTS 'gcd'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be safely removed while data may reference them.
    pass
