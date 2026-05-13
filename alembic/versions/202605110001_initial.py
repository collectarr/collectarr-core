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
    item_kind = postgresql.ENUM(
        "anime",
        "boardgame",
        "book",
        "bluray",
        "comic",
        "game",
        "manga",
        "movie",
        "music",
        "tv",
        name="item_kind",
    )
    external_provider = postgresql.ENUM(
        "anilist",
        "bgg",
        "comicvine",
        "gcd",
        "igdb",
        "musicbrainz",
        "openlibrary",
        "tmdb",
        name="external_provider",
    )
    item_kind.create(op.get_bind(), checkfirst=True)
    external_provider.create(op.get_bind(), checkfirst=True)
    item_kind = postgresql.ENUM(
        "anime",
        "boardgame",
        "book",
        "bluray",
        "comic",
        "game",
        "manga",
        "movie",
        "music",
        "tv",
        name="item_kind",
        create_type=False,
    )
    external_provider = postgresql.ENUM(
        "anilist",
        "bgg",
        "comicvine",
        "gcd",
        "igdb",
        "musicbrainz",
        "openlibrary",
        "tmdb",
        name="external_provider",
        create_type=False,
    )

    op.create_table(
        "franchises",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.Column("original_title", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["franchise_id"], ["franchises.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_series_franchise_id"), "series", ["franchise_id"])
    op.create_index(op.f("ix_series_country"), "series", ["country"])
    op.create_index(op.f("ix_series_language"), "series", ["language"])
    op.create_index(op.f("ix_series_slug"), "series", ["slug"])
    op.create_index(op.f("ix_series_status"), "series", ["status"])
    op.create_index(op.f("ix_series_title"), "series", ["title"])

    op.create_table(
        "volumes",
        sa.Column("series_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("volume_number", sa.Integer(), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.Column("release_type", sa.String(length=64), nullable=True),
        sa.Column("season_number", sa.Integer(), nullable=True),
        sa.Column("episode_number", sa.Integer(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["volume_id"], ["volumes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_items_kind_title", "items", ["kind", "title"])
    op.create_index(op.f("ix_items_item_number"), "items", ["item_number"])
    op.create_index(op.f("ix_items_episode_number"), "items", ["episode_number"])
    op.create_index(op.f("ix_items_release_type"), "items", ["release_type"])
    op.create_index(op.f("ix_items_season_number"), "items", ["season_number"])
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
        sa.Column("region", sa.String(length=32), nullable=True),
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
    op.create_index(op.f("ix_editions_region"), "editions", ["region"])
    op.create_index(op.f("ix_editions_upc"), "editions", ["upc"])

    op.create_table(
        "releases",
        sa.Column("edition_id", sa.UUID(), nullable=False),
        sa.Column("region", sa.String(length=32), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("external_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.Column("variant_type", sa.String(length=64), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("barcode", sa.String(length=32), nullable=True),
        sa.Column("isbn", sa.String(length=32), nullable=True),
        sa.Column("region", sa.String(length=32), nullable=True),
        sa.Column("platform", sa.String(length=64), nullable=True),
        sa.Column("cover_price_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("cover_image_key", sa.String(length=512), nullable=True),
        sa.Column("cover_image_url", sa.String(length=1024), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["edition_id"], ["editions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_variants_barcode"), "variants", ["barcode"])
    op.create_index(op.f("ix_variants_edition_id"), "variants", ["edition_id"])
    op.create_index(op.f("ix_variants_isbn"), "variants", ["isbn"])
    op.create_index(op.f("ix_variants_platform"), "variants", ["platform"])
    op.create_index(op.f("ix_variants_region"), "variants", ["region"])
    op.create_index(op.f("ix_variants_sku"), "variants", ["sku"])
    op.create_index(op.f("ix_variants_variant_type"), "variants", ["variant_type"])

    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_country"), "organizations", ["country"])
    op.create_index(op.f("ix_organizations_name"), "organizations", ["name"])
    op.create_index(op.f("ix_organizations_type"), "organizations", ["type"])

    op.create_table(
        "persons",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_persons_name"), "persons", ["name"])

    op.create_table(
        "tags",
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "name", name="uq_tags_kind_name"),
    )
    op.create_index(op.f("ix_tags_kind"), "tags", ["kind"])
    op.create_index(op.f("ix_tags_name"), "tags", ["name"])

    op.create_table(
        "entity_organizations",
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "organization_id",
            "role",
            name="uq_entity_organization_role",
        ),
    )
    op.create_index(
        "ix_entity_organizations_entity", "entity_organizations", ["entity_type", "entity_id"]
    )
    op.create_index(op.f("ix_entity_organizations_role"), "entity_organizations", ["role"])

    op.create_table(
        "entity_persons",
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "person_id",
            "role",
            name="uq_entity_person_role",
        ),
    )
    op.create_index("ix_entity_persons_entity", "entity_persons", ["entity_type", "entity_id"])
    op.create_index(op.f("ix_entity_persons_role"), "entity_persons", ["role"])

    op.create_table(
        "entity_tags",
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("tag_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "entity_id", "tag_id", name="uq_entity_tag"),
    )
    op.create_index("ix_entity_tags_entity", "entity_tags", ["entity_type", "entity_id"])

    op.create_table(
        "image_assets",
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("image_type", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("thumbnail_storage_key", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("phash", sa.String(length=128), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_image_assets_entity", "image_assets", ["entity_type", "entity_id"])
    op.create_index(op.f("ix_image_assets_image_type"), "image_assets", ["image_type"])
    op.create_index(op.f("ix_image_assets_phash"), "image_assets", ["phash"])
    op.create_index(op.f("ix_image_assets_provider"), "image_assets", ["provider"])


def downgrade() -> None:
    op.drop_index(op.f("ix_image_assets_provider"), table_name="image_assets")
    op.drop_index(op.f("ix_image_assets_phash"), table_name="image_assets")
    op.drop_index(op.f("ix_image_assets_image_type"), table_name="image_assets")
    op.drop_index("ix_image_assets_entity", table_name="image_assets")
    op.drop_table("image_assets")
    op.drop_index("ix_entity_tags_entity", table_name="entity_tags")
    op.drop_table("entity_tags")
    op.drop_index(op.f("ix_entity_persons_role"), table_name="entity_persons")
    op.drop_index("ix_entity_persons_entity", table_name="entity_persons")
    op.drop_table("entity_persons")
    op.drop_index(op.f("ix_entity_organizations_role"), table_name="entity_organizations")
    op.drop_index("ix_entity_organizations_entity", table_name="entity_organizations")
    op.drop_table("entity_organizations")
    op.drop_index(op.f("ix_tags_name"), table_name="tags")
    op.drop_index(op.f("ix_tags_kind"), table_name="tags")
    op.drop_table("tags")
    op.drop_index(op.f("ix_persons_name"), table_name="persons")
    op.drop_table("persons")
    op.drop_index(op.f("ix_organizations_type"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_country"), table_name="organizations")
    op.drop_table("organizations")
    op.drop_index(op.f("ix_variants_variant_type"), table_name="variants")
    op.drop_index(op.f("ix_variants_sku"), table_name="variants")
    op.drop_index(op.f("ix_variants_region"), table_name="variants")
    op.drop_index(op.f("ix_variants_platform"), table_name="variants")
    op.drop_index(op.f("ix_variants_isbn"), table_name="variants")
    op.drop_index(op.f("ix_variants_edition_id"), table_name="variants")
    op.drop_index(op.f("ix_variants_barcode"), table_name="variants")
    op.drop_table("variants")
    op.drop_index(op.f("ix_releases_region"), table_name="releases")
    op.drop_index(op.f("ix_releases_edition_id"), table_name="releases")
    op.drop_table("releases")
    op.drop_index(op.f("ix_editions_upc"), table_name="editions")
    op.drop_index(op.f("ix_editions_publisher"), table_name="editions")
    op.drop_index(op.f("ix_editions_region"), table_name="editions")
    op.drop_index(op.f("ix_editions_language"), table_name="editions")
    op.drop_index(op.f("ix_editions_item_id"), table_name="editions")
    op.drop_index(op.f("ix_editions_isbn"), table_name="editions")
    op.drop_table("editions")
    op.drop_index(op.f("ix_items_volume_id"), table_name="items")
    op.drop_index(op.f("ix_items_title"), table_name="items")
    op.drop_index(op.f("ix_items_sort_key"), table_name="items")
    op.drop_index(op.f("ix_items_season_number"), table_name="items")
    op.drop_index(op.f("ix_items_release_type"), table_name="items")
    op.drop_index(op.f("ix_items_item_number"), table_name="items")
    op.drop_index(op.f("ix_items_episode_number"), table_name="items")
    op.drop_index("ix_items_kind_title", table_name="items")
    op.drop_table("items")
    op.drop_index(op.f("ix_volumes_series_id"), table_name="volumes")
    op.drop_table("volumes")
    op.drop_index(op.f("ix_series_title"), table_name="series")
    op.drop_index(op.f("ix_series_status"), table_name="series")
    op.drop_index(op.f("ix_series_slug"), table_name="series")
    op.drop_index(op.f("ix_series_language"), table_name="series")
    op.drop_index(op.f("ix_series_franchise_id"), table_name="series")
    op.drop_index(op.f("ix_series_country"), table_name="series")
    op.drop_table("series")
    op.drop_index("ix_external_entity", table_name="external_provider_ids")
    op.drop_table("external_provider_ids")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_franchises_name"), table_name="franchises")
    op.drop_table("franchises")

    postgresql.ENUM(name="external_provider").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="item_kind").drop(op.get_bind(), checkfirst=True)
