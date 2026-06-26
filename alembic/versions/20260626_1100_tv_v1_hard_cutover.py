"""TV v1 hard cutover - delete legacy TV items.

Revision ID: 20260626_1100_tv_v1_hard_cutover
Revises: 20260626_1000_tv_v1_schema
Create Date: 2026-06-26 19:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260626_1100_tv_v1_hard_cutover"
down_revision: str | None = "20260626_1000_tv_v1_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove legacy TV items and provider links."""
    # Delete all tv items (kind='tv') and their related data will cascade
    op.execute(sa.text("DELETE FROM items WHERE kind = 'tv'"))


def downgrade() -> None:
    """Restore would require rebuilding from provider data (not implemented)."""
    # Hard cutover: cannot downgrade
    pass
