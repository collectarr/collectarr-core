"""remove personal tracking entries

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-23 23:55:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_tracking_entries_user_status", table_name="tracking_entries")
    op.drop_index("ix_tracking_entries_user_item", table_name="tracking_entries")
    op.drop_index("ix_tracking_entries_updated", table_name="tracking_entries")
    op.drop_index("ix_tracking_entries_owned_item", table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_variant_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_user_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_updated_at"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_status"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_source_type"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_owned_item_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_item_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_edition_id"), table_name="tracking_entries")
    op.drop_index(op.f("ix_tracking_entries_deleted_at"), table_name="tracking_entries")
    op.drop_table("tracking_entries")


def downgrade() -> None:
    raise NotImplementedError("Personal tracking entries remain out of collectarr-core")