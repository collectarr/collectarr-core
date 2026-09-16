"""Initial server schema (schema version 1).

The server database starts empty and this revision materializes the complete
current model metadata. Schema changes require recreating the database and
regenerating this baseline; no historical upgrade path is maintained.

This baseline already includes the relational-metadata model (per-kind typed
metadata, taxonomy/alias/link tables, music tracks) and the integrity hardening
(non-negative CHECKs, one-primary-per-parent partial unique indexes, and
foreign-key reverse indexes).

Revision ID: 1
Revises:
Create Date: 2026-06-24 18:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.models import Base

# revision identifiers, used by Alembic.
revision: str = "1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
