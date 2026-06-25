"""Remove legacy bluray item kind.

Revision ID: 20260625_1000
Revises: 20260624_1000
Create Date: 2026-06-25 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_1000"
down_revision: str | None = "20260624_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ITEM_KIND_VALUES = (
    "anime",
    "boardgame",
    "book",
    "collection",
    "comic",
    "game",
    "manga",
    "movie",
    "music",
    "tv",
)

_ITEM_KIND_VALUES_DOWNGRADE = (
    "anime",
    "boardgame",
    "book",
    "bluray",
    "collection",
    "comic",
    "game",
    "manga",
    "movie",
    "music",
    "tv",
)


def _replace_item_kind_enum(new_values: tuple[str, ...]) -> None:
    values_sql = ", ".join(f"'{value}'" for value in new_values)
    op.execute("ALTER TYPE item_kind RENAME TO item_kind_old")
    op.execute(f"CREATE TYPE item_kind AS ENUM ({values_sql})")
    op.execute(
        """
        DO $$
        DECLARE col record;
        BEGIN
            FOR col IN
                SELECT n.nspname AS schema_name,
                       c.relname AS table_name,
                       a.attname AS column_name
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                JOIN pg_namespace n ON c.relnamespace = n.oid
                JOIN pg_type t ON a.atttypid = t.oid
                WHERE t.typname = 'item_kind_old'
                  AND a.attnum > 0
                  AND NOT a.attisdropped
            LOOP
                EXECUTE format(
                    'ALTER TABLE %I.%I ALTER COLUMN %I TYPE item_kind USING %I::text::item_kind',
                    col.schema_name,
                    col.table_name,
                    col.column_name,
                    col.column_name
                );
            END LOOP;
        END $$;
        """
    )
    op.execute("DROP TYPE item_kind_old")


def upgrade() -> None:
    op.execute("DELETE FROM item_kind_metadata WHERE kind = 'bluray'")
    op.execute("DELETE FROM bundle_releases WHERE kind = 'bluray'")
    op.execute("DELETE FROM items WHERE kind = 'bluray'")
    op.execute("DROP TABLE IF EXISTS item_kind_metadata_bluray")
    _replace_item_kind_enum(_ITEM_KIND_VALUES)


def downgrade() -> None:
    _replace_item_kind_enum(_ITEM_KIND_VALUES_DOWNGRADE)
