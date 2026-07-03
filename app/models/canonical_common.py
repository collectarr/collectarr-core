from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    and_,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import (
    Base,
    ItemKind,
    TimestampMixin,
    UuidMixin,
)
from app.models.canonical_support import (  # noqa: F401
    AdminAuditLog,
    AdminReleaseMediaMappingRule,
    Character,
    CharacterAppearance,
    ComicSeriesRelation,
    EntityAlias,
    EntityLink,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    ImageAsset,
    ImageCacheEntry,
    MangaSeriesRelation,
    MetadataProposal,
    Organization,
    Person,
    ProviderIngestJob,
    ProviderPayloadSnapshot,
    StoryArc,
    StoryArcItem,
    Tag,
)


class ReleaseStatus(UuidMixin, TimestampMixin, Base):
    __tablename__ = "release_statuses"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class PhysicalFormatRef(UuidMixin, TimestampMixin, Base):
    __tablename__ = "physical_format_refs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    media_family: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class MetadataTaxonomy(UuidMixin, TimestampMixin, Base):
    __tablename__ = "metadata_taxonomies"
    __table_args__ = (
        CheckConstraint(
            "category IN ('genre', 'platform')",
            name="ck_metadata_taxonomies_category_valid",
        ),
    )

    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class BundleRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "bundle_releases"
    __table_args__ = (
        Index("ix_bundle_releases_kind_bundle_type", "kind", "bundle_type"),
        Index("ix_bundle_releases_format_region", "format", "region"),
    )

    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    bundle_type: Mapped[str | None] = mapped_column(String(64), index=True)
    format: Mapped[str | None] = mapped_column(String(64), index=True)
    variant_type: Mapped[str | None] = mapped_column(String(64), index=True)
    packaging_type: Mapped[str | None] = mapped_column(String(64), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    language: Mapped[str | None] = mapped_column(String(32), index=True)
    publisher: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(32), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    thumbnail_image_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_image_url: Mapped[str | None] = mapped_column(String(1024))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    components: Mapped[list["BundleReleaseComponent"]] = relationship(
        back_populates="bundle_release", cascade="all, delete-orphan"
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == BundleRelease.id,
            ExternalProviderId.entity_type == "bundle_release",
        ),
        viewonly=True,
    )


class BundleReleaseComponent(UuidMixin, TimestampMixin, Base):
    __tablename__ = "bundle_release_components"
    __table_args__ = (
        UniqueConstraint(
            "bundle_release_id",
            "entity_type",
            "entity_id",
            "role",
            "disc_number",
            "sequence_number",
            name="uq_bundle_release_component_membership",
        ),
        Index(
            "ix_bundle_release_components_bundle_sequence",
            "bundle_release_id",
            "disc_number",
            "sequence_number",
        ),
        Index("ix_bundle_release_components_entity", "entity_type", "entity_id"),
    )

    bundle_release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bundle_releases.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    disc_number: Mapped[int | None] = mapped_column(Integer, index=True)
    disc_label: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    bundle_release: Mapped[BundleRelease] = relationship(back_populates="components")
