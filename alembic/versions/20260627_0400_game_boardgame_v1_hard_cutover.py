"""Hard cutover to game and boardgame v1 schema.

Revision ID: 20260627_0400
Revises: 20260627_0300
Create Date: 2026-06-27 04:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260627_0400"
down_revision: str | None = "20260627_0300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM items WHERE kind IN ('game', 'boardgame')")
    op.execute(
        """
        DELETE FROM external_provider_ids
        WHERE entity_type = 'item'
          AND NOT EXISTS (
              SELECT 1
              FROM items
              WHERE items.id = external_provider_ids.entity_id
          )
        """
    )
    op.execute(
        """
        DELETE FROM provider_payload_snapshots
        WHERE entity_type = 'item'
          AND NOT EXISTS (
              SELECT 1
              FROM items
              WHERE items.id = provider_payload_snapshots.entity_id
          )
        """
    )


def downgrade() -> None:
    pass
