"""add user role column

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-20 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    role_enum = postgresql.ENUM("viewer", "editor", "admin", name="user_role")
    role_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.Enum("viewer", "editor", "admin", name="user_role"),
            nullable=False,
            server_default="viewer",
        ),
    )
    op.execute("UPDATE users SET role = 'admin' WHERE is_admin = true")


def downgrade() -> None:
    op.drop_column("users", "role")
    role_enum = postgresql.ENUM("viewer", "editor", "admin", name="user_role")
    role_enum.drop(op.get_bind(), checkfirst=True)
