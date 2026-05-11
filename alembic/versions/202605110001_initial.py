"""initial collector schema

Revision ID: 202605110001
Revises:
Create Date: 2026-05-11 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605110001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    item_kind = postgresql.ENUM("comic", "game", "bluray", "manga", name="item_kind")
    external_provider = postgresql.ENUM("comicvine", "igdb", "tmdb", name="external_provider")
    sync_action = postgresql.ENUM("upsert", "delete", name="sync_action")
    item_kind.create(op.get_bind(), checkfirst=True)
    external_provider.create(op.get_bind(), checkfirst=True)
    sync_action.create(op.get_bind(), checkfirst=True)
    item_kind = postgresql.ENUM(
        "comic", "game", "bluray", "manga", name="item_kind", create_type=False
    )
    external_provider = postgresql.ENUM(
        "comicvine", "igdb", "tmdb", name="external_provider", create_type=False
    )
    sync_action = postgresql.ENUM("upsert", "delete", name="sync_action", create_type=False)

    op.create_table(
        "franchises",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_franchises_name"), "franchises", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "external_provider_ids",
        sa.Column("provider", external_provider, nullable=False),
        sa.Column("provider_item_id", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("raw_url", sa.String(length=1024), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_item_id", name="uq_provider_provider_item_id"),
    )
    op.create_index("ix_external_entity", "external_provider_ids", ["entity_type", "entity_id"])

    op.create_table(
        "series",
        sa.Column("franchise_id", sa.UUID(), nullable=True),
        sa.Column("kind", item_kind, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["franchise_id"], ["franchises.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_series_franchise_id"), "series", ["franchise_id"])
    op.create_index(op.f("ix_series_slug"), "series", ["slug"])
    op.create_index(op.f("ix_series_title"), "series", ["title"])

    op.create_table(
        "sync_changes",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.String(length=120), nullable=True),
        sa.Column("action", sync_action, nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sync_changes_changed_at"), "sync_changes", ["changed_at"])
    op.create_index(op.f("ix_sync_changes_entity_id"), "sync_changes", ["entity_id"])
    op.create_index(op.f("ix_sync_changes_entity_type"), "sync_changes", ["entity_type"])
    op.create_index(op.f("ix_sync_changes_device_id"), "sync_changes", ["device_id"])
    op.create_index("ix_sync_user_changed", "sync_changes", ["user_id", "changed_at"])
    op.create_index(op.f("ix_sync_changes_user_id"), "sync_changes", ["user_id"])

    op.create_table(
        "tags",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_tag_name"),
    )

    op.create_table(
        "user_collections",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_collection_name"),
    )
    op.create_index(op.f("ix_user_collections_user_id"), "user_collections", ["user_id"])

    op.create_table(
        "volumes",
        sa.Column("series_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("volume_number", sa.Integer(), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_volumes_series_id"), "volumes", ["series_id"])

    op.create_table(
        "items",
        sa.Column("volume_id", sa.UUID(), nullable=True),
        sa.Column("kind", item_kind, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("item_number", sa.String(length=64), nullable=True),
        sa.Column("sort_key", sa.String(length=255), nullable=True),
        sa.Column("synopsis", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["volume_id"], ["volumes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_items_kind_title", "items", ["kind", "title"])
    op.create_index(op.f("ix_items_item_number"), "items", ["item_number"])
    op.create_index(op.f("ix_items_sort_key"), "items", ["sort_key"])
    op.create_index(op.f("ix_items_title"), "items", ["title"])
    op.create_index(op.f("ix_items_volume_id"), "items", ["volume_id"])

    op.create_table(
        "editions",
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("format", sa.String(length=100), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("isbn", sa.String(length=32), nullable=True),
        sa.Column("upc", sa.String(length=32), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_editions_isbn"), "editions", ["isbn"])
    op.create_index(op.f("ix_editions_item_id"), "editions", ["item_id"])
    op.create_index(op.f("ix_editions_language"), "editions", ["language"])
    op.create_index(op.f("ix_editions_publisher"), "editions", ["publisher"])
    op.create_index(op.f("ix_editions_upc"), "editions", ["upc"])

    op.create_table(
        "wishlist_items",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("edition_id", sa.UUID(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["edition_id"], ["editions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "releases",
        sa.Column("edition_id", sa.UUID(), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("external_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["edition_id"], ["editions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_releases_edition_id"), "releases", ["edition_id"])
    op.create_index(op.f("ix_releases_region"), "releases", ["region"])

    op.create_table(
        "variants",
        sa.Column("edition_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["edition_id"], ["editions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_variants_edition_id"), "variants", ["edition_id"])
    op.create_index(op.f("ix_variants_sku"), "variants", ["sku"])

    op.create_table(
        "owned_items",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("collection_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("edition_id", sa.UUID(), nullable=True),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("condition", sa.String(length=64), nullable=True),
        sa.Column("grade", sa.String(length=64), nullable=True),
        sa.Column("acquired_from", sa.String(length=255), nullable=True),
        sa.Column("purchase_price_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("personal_notes", sa.Text(), nullable=True),
        sa.Column("client_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["user_collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["edition_id"], ["editions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["variants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_owned_items_collection_id"), "owned_items", ["collection_id"])
    op.create_index(op.f("ix_owned_items_deleted_at"), "owned_items", ["deleted_at"])
    op.create_index(op.f("ix_owned_items_edition_id"), "owned_items", ["edition_id"])
    op.create_index(op.f("ix_owned_items_item_id"), "owned_items", ["item_id"])
    op.create_index("ix_owned_user_updated", "owned_items", ["user_id", "updated_at"])
    op.create_index(op.f("ix_owned_items_user_id"), "owned_items", ["user_id"])
    op.create_index(op.f("ix_owned_items_variant_id"), "owned_items", ["variant_id"])

    op.create_table(
        "notes",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("owned_item_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owned_item_id"], ["owned_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "owned_item_tags",
        sa.Column("owned_item_id", sa.UUID(), nullable=False),
        sa.Column("tag_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["owned_item_id"], ["owned_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("owned_item_id", "tag_id"),
    )


def downgrade() -> None:
    op.drop_table("owned_item_tags")
    op.drop_table("notes")
    op.drop_index(op.f("ix_owned_items_variant_id"), table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_user_id"), table_name="owned_items")
    op.drop_index("ix_owned_user_updated", table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_item_id"), table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_edition_id"), table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_deleted_at"), table_name="owned_items")
    op.drop_index(op.f("ix_owned_items_collection_id"), table_name="owned_items")
    op.drop_table("owned_items")
    op.drop_index(op.f("ix_variants_sku"), table_name="variants")
    op.drop_index(op.f("ix_variants_edition_id"), table_name="variants")
    op.drop_table("variants")
    op.drop_index(op.f("ix_releases_region"), table_name="releases")
    op.drop_index(op.f("ix_releases_edition_id"), table_name="releases")
    op.drop_table("releases")
    op.drop_table("wishlist_items")
    op.drop_index(op.f("ix_editions_upc"), table_name="editions")
    op.drop_index(op.f("ix_editions_publisher"), table_name="editions")
    op.drop_index(op.f("ix_editions_language"), table_name="editions")
    op.drop_index(op.f("ix_editions_item_id"), table_name="editions")
    op.drop_index(op.f("ix_editions_isbn"), table_name="editions")
    op.drop_table("editions")
    op.drop_index(op.f("ix_items_volume_id"), table_name="items")
    op.drop_index(op.f("ix_items_title"), table_name="items")
    op.drop_index(op.f("ix_items_sort_key"), table_name="items")
    op.drop_index(op.f("ix_items_item_number"), table_name="items")
    op.drop_index("ix_items_kind_title", table_name="items")
    op.drop_table("items")
    op.drop_index(op.f("ix_volumes_series_id"), table_name="volumes")
    op.drop_table("volumes")
    op.drop_index(op.f("ix_user_collections_user_id"), table_name="user_collections")
    op.drop_table("user_collections")
    op.drop_table("tags")
    op.drop_index(op.f("ix_sync_changes_user_id"), table_name="sync_changes")
    op.drop_index("ix_sync_user_changed", table_name="sync_changes")
    op.drop_index(op.f("ix_sync_changes_device_id"), table_name="sync_changes")
    op.drop_index(op.f("ix_sync_changes_entity_type"), table_name="sync_changes")
    op.drop_index(op.f("ix_sync_changes_entity_id"), table_name="sync_changes")
    op.drop_index(op.f("ix_sync_changes_changed_at"), table_name="sync_changes")
    op.drop_table("sync_changes")
    op.drop_index(op.f("ix_series_title"), table_name="series")
    op.drop_index(op.f("ix_series_slug"), table_name="series")
    op.drop_index(op.f("ix_series_franchise_id"), table_name="series")
    op.drop_table("series")
    op.drop_index("ix_external_entity", table_name="external_provider_ids")
    op.drop_table("external_provider_ids")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_franchises_name"), table_name="franchises")
    op.drop_table("franchises")

    postgresql.ENUM(name="sync_action").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="external_provider").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="item_kind").drop(op.get_bind(), checkfirst=True)
