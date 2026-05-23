"""add bundle release catalog tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-24 00:25:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bundle_releases",
        sa.Column("kind", postgresql.ENUM(name="item_kind", create_type=False), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("bundle_type", sa.String(length=64), nullable=True),
        sa.Column("franchise_id", sa.UUID(), nullable=True),
        sa.Column("series_id", sa.UUID(), nullable=True),
        sa.Column("volume_id", sa.UUID(), nullable=True),
        sa.Column("primary_item_id", sa.UUID(), nullable=True),
        sa.Column("format", sa.String(length=64), nullable=True),
        sa.Column("variant_type", sa.String(length=64), nullable=True),
        sa.Column("packaging_type", sa.String(length=64), nullable=True),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("barcode", sa.String(length=32), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("thumbnail_image_key", sa.String(length=512), nullable=True),
        sa.Column("thumbnail_image_url", sa.String(length=1024), nullable=True),
        sa.Column("external_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["franchise_id"], ["franchises.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["primary_item_id"], ["items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["volume_id"], ["volumes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bundle_releases_barcode"), "bundle_releases", ["barcode"], unique=False)
    op.create_index(op.f("ix_bundle_releases_bundle_type"), "bundle_releases", ["bundle_type"], unique=False)
    op.create_index(op.f("ix_bundle_releases_format"), "bundle_releases", ["format"], unique=False)
    op.create_index(
        "ix_bundle_releases_format_region", "bundle_releases", ["format", "region"], unique=False
    )
    op.create_index(op.f("ix_bundle_releases_franchise_id"), "bundle_releases", ["franchise_id"], unique=False)
    op.create_index(op.f("ix_bundle_releases_kind"), "bundle_releases", ["kind"], unique=False)
    op.create_index(
        "ix_bundle_releases_kind_bundle_type",
        "bundle_releases",
        ["kind", "bundle_type"],
        unique=False,
    )
    op.create_index(op.f("ix_bundle_releases_language"), "bundle_releases", ["language"], unique=False)
    op.create_index(op.f("ix_bundle_releases_packaging_type"), "bundle_releases", ["packaging_type"], unique=False)
    op.create_index(op.f("ix_bundle_releases_primary_item_id"), "bundle_releases", ["primary_item_id"], unique=False)
    op.create_index(op.f("ix_bundle_releases_region"), "bundle_releases", ["region"], unique=False)
    op.create_index(op.f("ix_bundle_releases_release_date"), "bundle_releases", ["release_date"], unique=False)
    op.create_index(
        "ix_bundle_releases_series_release_date",
        "bundle_releases",
        ["series_id", "release_date"],
        unique=False,
    )
    op.create_index(op.f("ix_bundle_releases_series_id"), "bundle_releases", ["series_id"], unique=False)
    op.create_index(op.f("ix_bundle_releases_sku"), "bundle_releases", ["sku"], unique=False)
    op.create_index(op.f("ix_bundle_releases_variant_type"), "bundle_releases", ["variant_type"], unique=False)
    op.create_index(op.f("ix_bundle_releases_volume_id"), "bundle_releases", ["volume_id"], unique=False)

    op.create_table(
        "bundle_release_items",
        sa.Column("bundle_release_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("disc_number", sa.Integer(), nullable=True),
        sa.Column("disc_label", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bundle_release_id"], ["bundle_releases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bundle_release_id",
            "item_id",
            "role",
            "disc_number",
            "sequence_number",
            name="uq_bundle_release_item_membership",
        ),
    )
    op.create_index(
        "ix_bundle_release_items_bundle_sequence",
        "bundle_release_items",
        ["bundle_release_id", "disc_number", "sequence_number"],
        unique=False,
    )
    op.create_index(op.f("ix_bundle_release_items_bundle_release_id"), "bundle_release_items", ["bundle_release_id"], unique=False)
    op.create_index(op.f("ix_bundle_release_items_disc_number"), "bundle_release_items", ["disc_number"], unique=False)
    op.create_index(op.f("ix_bundle_release_items_item_id"), "bundle_release_items", ["item_id"], unique=False)
    op.create_index(op.f("ix_bundle_release_items_role"), "bundle_release_items", ["role"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bundle_release_items_role"), table_name="bundle_release_items")
    op.drop_index(op.f("ix_bundle_release_items_item_id"), table_name="bundle_release_items")
    op.drop_index(op.f("ix_bundle_release_items_disc_number"), table_name="bundle_release_items")
    op.drop_index(op.f("ix_bundle_release_items_bundle_release_id"), table_name="bundle_release_items")
    op.drop_index("ix_bundle_release_items_bundle_sequence", table_name="bundle_release_items")
    op.drop_table("bundle_release_items")

    op.drop_index(op.f("ix_bundle_releases_volume_id"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_variant_type"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_sku"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_series_id"), table_name="bundle_releases")
    op.drop_index("ix_bundle_releases_series_release_date", table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_release_date"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_region"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_primary_item_id"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_packaging_type"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_language"), table_name="bundle_releases")
    op.drop_index("ix_bundle_releases_kind_bundle_type", table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_kind"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_franchise_id"), table_name="bundle_releases")
    op.drop_index("ix_bundle_releases_format_region", table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_format"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_bundle_type"), table_name="bundle_releases")
    op.drop_index(op.f("ix_bundle_releases_barcode"), table_name="bundle_releases")
    op.drop_table("bundle_releases")