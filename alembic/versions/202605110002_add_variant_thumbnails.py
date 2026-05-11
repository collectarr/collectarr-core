"""add variant thumbnail columns

Revision ID: 202605110002
Revises: 202605110001
Create Date: 2026-05-11 19:34:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202605110002"
down_revision: str | None = "202605110001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("alter table variants add column if not exists thumbnail_image_key varchar(512)")
    op.execute("alter table variants add column if not exists thumbnail_image_url varchar(1024)")


def downgrade() -> None:
    op.execute("alter table variants drop column if exists thumbnail_image_url")
    op.execute("alter table variants drop column if exists thumbnail_image_key")
