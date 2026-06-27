"""Fix comic_works.volume_id to remove unique constraint.

Revision ID: 20260625_2800
Revises: 20260625_2700
Create Date: 2026-06-25 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_2800"
down_revision: str | None = "20260625_2700"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop unique constraint if it exists (uq_comic_works_volume_id)
    with suppress(Exception):
        op.drop_constraint("uq_comic_works_volume_id", "comic_works")

    # Drop unique index if it exists (ix_comic_works_volume_id_unique)
    with suppress(Exception):
        op.drop_index("ix_comic_works_volume_id_unique", "comic_works")


def downgrade() -> None:
    pass
