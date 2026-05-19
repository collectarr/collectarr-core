"""add story arcs and characters tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "story_arcs",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("publisher", sa.String(255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "publisher", name="uq_story_arcs_name_publisher"),
    )
    op.create_index(op.f("ix_story_arcs_name"), "story_arcs", ["name"], unique=False)
    op.create_index(op.f("ix_story_arcs_publisher"), "story_arcs", ["publisher"], unique=False)

    op.create_table(
        "characters",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(1024), nullable=True),
        sa.Column("first_appearance_item_id", sa.UUID(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["first_appearance_item_id"],
            ["items.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_characters_name"), "characters", ["name"], unique=True)
    op.create_index(
        op.f("ix_characters_first_appearance_item_id"),
        "characters",
        ["first_appearance_item_id"],
        unique=False,
    )

    op.create_table(
        "story_arc_items",
        sa.Column("story_arc_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_arc_id"], ["story_arcs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_arc_id", "item_id", name="uq_story_arc_item"),
    )
    op.create_index(
        "ix_story_arc_items_story_arc",
        "story_arc_items",
        ["story_arc_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_arc_items_item",
        "story_arc_items",
        ["item_id"],
        unique=False,
    )

    op.create_table(
        "character_appearances",
        sa.Column("character_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "item_id", name="uq_character_appearance"),
    )
    op.create_index(
        "ix_character_appearances_character",
        "character_appearances",
        ["character_id"],
        unique=False,
    )
    op.create_index(
        "ix_character_appearances_item",
        "character_appearances",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_character_appearances_role"),
        "character_appearances",
        ["role"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_character_appearances_role"), table_name="character_appearances")
    op.drop_index("ix_character_appearances_item", table_name="character_appearances")
    op.drop_index("ix_character_appearances_character", table_name="character_appearances")
    op.drop_table("character_appearances")

    op.drop_index("ix_story_arc_items_item", table_name="story_arc_items")
    op.drop_index("ix_story_arc_items_story_arc", table_name="story_arc_items")
    op.drop_table("story_arc_items")

    op.drop_index(
        op.f("ix_characters_first_appearance_item_id"),
        table_name="characters",
    )
    op.drop_index(op.f("ix_characters_name"), table_name="characters")
    op.drop_table("characters")

    op.drop_index(op.f("ix_story_arcs_publisher"), table_name="story_arcs")
    op.drop_index(op.f("ix_story_arcs_name"), table_name="story_arcs")
    op.drop_table("story_arcs")
