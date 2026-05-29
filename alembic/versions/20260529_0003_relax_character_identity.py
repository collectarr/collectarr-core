"""Relax Character identity to provider-aware canonical names.

Revision ID: 20260529_0003
Revises: 20260529_0002
Create Date: 2026-05-29 00:00:03
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260529_0003"
down_revision: str | None = "20260529_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE characters ADD COLUMN IF NOT EXISTS canonical_name VARCHAR(255)")
    op.execute(
        """
        UPDATE characters
        SET canonical_name = LOWER(BTRIM(name))
        WHERE canonical_name IS NULL AND name IS NOT NULL
        """
    )
    op.execute("ALTER TABLE characters DROP CONSTRAINT IF EXISTS characters_name_key")
    op.execute("DROP INDEX IF EXISTS ix_characters_canonical_name")
    op.execute("CREATE INDEX IF NOT EXISTS ix_characters_canonical_name ON characters (canonical_name)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_characters_canonical_name")
    op.execute("ALTER TABLE characters DROP COLUMN IF EXISTS canonical_name")
    op.execute("ALTER TABLE characters ADD CONSTRAINT characters_name_key UNIQUE (name)")