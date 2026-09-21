"""Add provider-independent canonical correction proposals."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "2"
down_revision: str | None = "1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "canonical_correction_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
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
                name="item_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("base_revision", sa.String(length=128), nullable=True),
        sa.Column("base_hash", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "base_revision IS NOT NULL OR base_hash IS NOT NULL",
            name="ck_canonical_correction_proposals_base_present",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_canonical_correction_proposals_kind",
        "canonical_correction_proposals",
        ["kind"],
    )
    op.create_index(
        "ix_canonical_correction_proposals_status",
        "canonical_correction_proposals",
        ["status"],
    )
    op.create_index(
        "ix_canonical_correction_proposals_target",
        "canonical_correction_proposals",
        ["kind", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_canonical_correction_proposals_status_created",
        "canonical_correction_proposals",
        ["status", "created_at"],
    )

    op.create_table(
        "canonical_correction_proposal_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("value_type", sa.String(length=16), nullable=False),
        sa.Column("string_value", sa.Text(), nullable=True),
        sa.Column("integer_value", sa.BigInteger(), nullable=True),
        sa.Column("decimal_value", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("date_value", sa.Date(), nullable=True),
        sa.Column("datetime_value", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uuid_value", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["canonical_correction_proposals.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id",
            "path",
            name="uq_canonical_correction_proposal_values_path",
        ),
    )
    op.create_index(
        "ix_canonical_correction_proposal_values_proposal",
        "canonical_correction_proposal_values",
        ["proposal_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_canonical_correction_proposal_values_proposal",
        table_name="canonical_correction_proposal_values",
    )
    op.drop_table("canonical_correction_proposal_values")
    op.drop_index(
        "ix_canonical_correction_proposals_status_created",
        table_name="canonical_correction_proposals",
    )
    op.drop_index(
        "ix_canonical_correction_proposals_target",
        table_name="canonical_correction_proposals",
    )
    op.drop_index(
        "ix_canonical_correction_proposals_status",
        table_name="canonical_correction_proposals",
    )
    op.drop_index(
        "ix_canonical_correction_proposals_kind",
        table_name="canonical_correction_proposals",
    )
    op.drop_table("canonical_correction_proposals")
