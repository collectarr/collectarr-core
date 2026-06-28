"""Restore shared taxonomy links for genres and platforms.

Revision ID: 20260627_0200
Revises: 20260627_0100
Create Date: 2026-06-27 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert

# revision identifiers, used by Alembic.
revision: str = "20260627_0200"
down_revision: str | None = "20260627_0100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metadata_taxonomies",
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('genre', 'platform')",
            name="ck_metadata_taxonomies_category_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "normalized_name", name="uq_metadata_taxonomies_category_normalized"),
    )
    op.create_index("ix_metadata_taxonomies_category", "metadata_taxonomies", ["category"], unique=False)
    op.create_index(
        "ix_metadata_taxonomies_normalized_name",
        "metadata_taxonomies",
        ["normalized_name"],
        unique=False,
    )

    op.create_table(
        "item_kind_metadata_taxonomies",
        sa.Column("item_kind_metadata_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("taxonomy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_kind_metadata_id"], ["item_kind_metadata.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["taxonomy_id"], ["metadata_taxonomies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "item_kind_metadata_id",
            "taxonomy_id",
            "category",
            name="uq_item_kind_metadata_taxonomy_link",
        ),
    )
    op.create_index(
        "ix_item_kind_metadata_taxonomies_owner_category_position",
        "item_kind_metadata_taxonomies",
        ["item_kind_metadata_id", "category", "position"],
        unique=False,
    )

    bind = op.get_bind()
    metadata_rows = bind.execute(
        sa.text(
            """
            SELECT id, metadata_json
            FROM item_kind_metadata
            WHERE metadata_json IS NOT NULL
            """
        )
    ).mappings().all()

    now = datetime.now(UTC)
    taxonomy_cache: dict[tuple[str, str], str] = {}

    def _taxonomy_id(category: str, name: str) -> str:
        key = (category, name.casefold())
        cached = taxonomy_cache.get(key)
        if cached is not None:
            return cached
        stmt = pg_insert(sa.table(
            "metadata_taxonomies",
            sa.column("category"),
            sa.column("name"),
            sa.column("normalized_name"),
            sa.column("id"),
            sa.column("created_at"),
            sa.column("updated_at"),
        )).values(
            category=category,
            name=name,
            normalized_name=name.casefold(),
            id=sa.func.gen_random_uuid(),
            created_at=now,
            updated_at=now,
        ).on_conflict_do_nothing(index_elements=["category", "normalized_name"])
        bind.execute(stmt)
        taxonomy_id = bind.execute(
            sa.text(
                """
                SELECT id
                FROM metadata_taxonomies
                WHERE category = :category AND normalized_name = :normalized_name
                """
            ),
            {"category": category, "normalized_name": name.casefold()},
        ).scalar_one()
        taxonomy_cache[key] = str(taxonomy_id)
        return str(taxonomy_id)

    for row in metadata_rows:
        metadata_json = row["metadata_json"]
        if not isinstance(metadata_json, dict):
            continue
        for category, key in (("genre", "genres"), ("platform", "platforms")):
            values = metadata_json.get(key)
            if not isinstance(values, list):
                continue
            deduped: list[str] = []
            seen: set[str] = set()
            for raw in values:
                text = str(raw or "").strip()
                if not text:
                    continue
                normalized = text.casefold()
                if normalized in seen:
                    continue
                seen.add(normalized)
                deduped.append(text)
            for position, text in enumerate(deduped):
                taxonomy_id = _taxonomy_id(category, text)
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO item_kind_metadata_taxonomies
                            (id, item_kind_metadata_id, taxonomy_id, category, position, created_at, updated_at)
                        VALUES
                            (gen_random_uuid(), :item_kind_metadata_id, :taxonomy_id, :category, :position, :created_at, :updated_at)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {
                        "item_kind_metadata_id": row["id"],
                        "taxonomy_id": taxonomy_id,
                        "category": category,
                        "position": position,
                        "created_at": now,
                        "updated_at": now,
                    },
                )

    bind.execute(
        sa.text(
            """
            UPDATE item_kind_metadata
            SET metadata_json = metadata_json - 'genres' - 'platforms'
            WHERE metadata_json ? 'genres' OR metadata_json ? 'platforms'
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_item_kind_metadata_taxonomies_owner_category_position", table_name="item_kind_metadata_taxonomies")
    op.drop_table("item_kind_metadata_taxonomies")
    op.drop_index("ix_metadata_taxonomies_normalized_name", table_name="metadata_taxonomies")
    op.drop_index("ix_metadata_taxonomies_category", table_name="metadata_taxonomies")
    op.drop_table("metadata_taxonomies")
