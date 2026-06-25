"""Hard cutover to books v1 schema.

Revision ID: 20260625_1700
Revises: 20260625_1600
Create Date: 2026-06-25 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_1700"
down_revision: str | None = "20260625_1600"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _drop_fk_if_exists(table_name: str, constrained_columns: tuple[str, ...]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        cols = tuple(fk.get("constrained_columns") or [])
        if cols == constrained_columns and fk.get("name"):
            op.drop_constraint(str(fk["name"]), table_name, type_="foreignkey")


def upgrade() -> None:
    op.execute("DELETE FROM items WHERE kind = 'book'")
    op.execute(
        """
        DELETE FROM external_provider_ids ep
        WHERE ep.entity_type = 'item'
          AND NOT EXISTS (
              SELECT 1
              FROM items i
              WHERE i.id = ep.entity_id
          )
        """
    )
    op.execute(
        """
        UPDATE book_works
        SET subtitle = NULL
        WHERE metadata_json IS NOT NULL
          AND metadata_json ? 'backfilled_from_item'
        """
    )
    if _has_index("book_works", "ix_book_works_generic_item_id"):
        op.drop_index("ix_book_works_generic_item_id", table_name="book_works")
    if _has_column("book_works", "generic_item_id"):
        _drop_fk_if_exists("book_works", ("generic_item_id",))
        op.drop_column("book_works", "generic_item_id")

    if _has_index("book_editions", "ix_book_editions_generic_edition_id"):
        op.drop_index("ix_book_editions_generic_edition_id", table_name="book_editions")
    if _has_column("book_editions", "generic_edition_id"):
        _drop_fk_if_exists("book_editions", ("generic_edition_id",))
        op.drop_column("book_editions", "generic_edition_id")


def downgrade() -> None:
    if not _has_column("book_works", "generic_item_id"):
        op.add_column(
            "book_works",
            sa.Column("generic_item_id", sa.UUID(), nullable=True),
        )
    if not _has_index("book_works", "ix_book_works_generic_item_id"):
        op.create_index("ix_book_works_generic_item_id", "book_works", ["generic_item_id"], unique=False)

    if not _has_column("book_editions", "generic_edition_id"):
        op.add_column(
            "book_editions",
            sa.Column("generic_edition_id", sa.UUID(), nullable=True),
        )
    if not _has_index("book_editions", "ix_book_editions_generic_edition_id"):
        op.create_index(
            "ix_book_editions_generic_edition_id",
            "book_editions",
            ["generic_edition_id"],
            unique=False,
        )
