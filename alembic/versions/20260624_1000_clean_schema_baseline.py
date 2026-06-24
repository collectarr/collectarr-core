"""Clean schema baseline after typed metadata redesign.

Revision ID: 20260624_1000
Revises:
Create Date: 2026-06-24 18:10:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260624_1000"
down_revision: str | None = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline-only migration: schema bootstrap is handled by metadata create_all.
    pass


def downgrade() -> None:
    raise NotImplementedError("Baseline revision cannot be downgraded.")
