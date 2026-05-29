"""Pre-Alembic baseline for existing databases.

Revision ID: 20260529_0001
Revises:
Create Date: 2026-05-29 00:00:01
"""

from collections.abc import Sequence


revision: str = "20260529_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass