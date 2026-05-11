"""drop central personal user data

Revision ID: 202605110002
Revises: 202605110001
Create Date: 2026-05-11 14:05:00.000000
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605110002"
down_revision: str | None = "202605110001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("owned_item_tags")

    op.drop_table("notes")

    op.drop_index(op.f("ix_owned_items_variant_id"), table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_user_id"), table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_item_id"), table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_edition_id"), table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_deleted_at"), table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_collection_id"), table_name="owned_items")
    op.drop_index("ix_owned_user_updated", table_name="owned_items")
    op.drop_table("owned_items")

    op.drop_table("wishlist_items")

    op.drop_table("tags")

    op.drop_index(op.f("ix_user_collections_user_id"), table_name="user_collections")
    op.drop_table("user_collections")

    op.drop_index(op.f("ix_sync_changes_user_id"), table_name="sync_changes")
    op.drop_index("ix_sync_user_changed", table_name="sync_changes")
    op.drop_index(op.f("ix_sync_changes_entity_type"), table_name="sync_changes")
    op.drop_index(op.f("ix_sync_changes_entity_id"), table_name="sync_changes")
    op.drop_index(op.f("ix_sync_changes_device_id"), table_name="sync_changes")
    op.drop_index(op.f("ix_sync_changes_changed_at"), table_name="sync_changes")
    op.drop_table("sync_changes")
    postgresql.ENUM(name="sync_action").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise NotImplementedError("Downgrade would recreate removed central personal-data tables without data")
