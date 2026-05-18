"""add series relations

Revision ID: 202605180001
Revises: 202605150001
Create Date: 2026-05-18 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605180001"
down_revision: str | None = "202605150001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

series_relation_type = sa.Enum(
    "sequel",
    "prequel",
    "side_story",
    "spin_off",
    "parent",
    "adaptation",
    "alternative",
    "summary",
    "compilation",
    "other",
    name="series_relation_type",
)


def upgrade() -> None:
    series_relation_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "series_relations",
        sa.Column("source_series_id", sa.UUID(), nullable=False),
        sa.Column("target_series_id", sa.UUID(), nullable=False),
        sa.Column("relation_type", series_relation_type, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_series_id"], ["series.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_series_id"], ["series.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_series_id",
            "target_series_id",
            "relation_type",
            name="uq_series_relations_source_target_type",
        ),
    )
    op.create_index(
        "ix_series_relations_source",
        "series_relations",
        ["source_series_id"],
    )
    op.create_index(
        "ix_series_relations_target",
        "series_relations",
        ["target_series_id"],
    )
    op.create_index(
        "ix_series_relations_type",
        "series_relations",
        ["relation_type"],
    )


def downgrade() -> None:
    op.drop_table("series_relations")
    series_relation_type.drop(op.get_bind(), checkfirst=True)
