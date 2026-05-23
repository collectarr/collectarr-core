import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ExternalProvider, ItemKind, SeriesRelationType, TimestampMixin, UuidMixin


class Franchise(UuidMixin, TimestampMixin, Base):
    __tablename__ = "franchises"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Series(UuidMixin, TimestampMixin, Base):
    __tablename__ = "series"

    franchise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("franchises.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    original_title: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    country: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    franchise: Mapped[Franchise | None] = relationship()
    volumes: Mapped[list["Volume"]] = relationship(back_populates="series")


class Volume(UuidMixin, TimestampMixin, Base):
    __tablename__ = "volumes"

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    volume_number: Mapped[int | None]
    start_year: Mapped[int | None]
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[Series] = relationship(back_populates="volumes")
    items: Mapped[list["Item"]] = relationship(back_populates="volume")


class Item(UuidMixin, TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (Index("ix_items_kind_title", "kind", "title"),)

    volume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("volumes.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    item_number: Mapped[str | None] = mapped_column(String(64), index=True)
    sort_key: Mapped[str | None] = mapped_column(String(255), index=True)
    synopsis: Mapped[str | None] = mapped_column(Text)
    release_type: Mapped[str | None] = mapped_column(String(64), index=True)
    season_number: Mapped[int | None] = mapped_column(Integer, index=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, index=True)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    volume: Mapped[Volume | None] = relationship(back_populates="items")
    editions: Mapped[list["Edition"]] = relationship(back_populates="item")


class Edition(UuidMixin, TimestampMixin, Base):
    __tablename__ = "editions"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str | None] = mapped_column(String(100))
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    isbn: Mapped[str | None] = mapped_column(String(32), index=True)
    upc: Mapped[str | None] = mapped_column(String(32), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    release_date: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    item: Mapped[Item] = relationship(back_populates="editions")
    variants: Mapped[list["Variant"]] = relationship(back_populates="edition")
    releases: Mapped[list["Release"]] = relationship(back_populates="edition")


class Variant(UuidMixin, TimestampMixin, Base):
    __tablename__ = "variants"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editions.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_type: Mapped[str | None] = mapped_column(String(64), index=True)
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(32), index=True)
    isbn: Mapped[str | None] = mapped_column(String(32), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    platform: Mapped[str | None] = mapped_column(String(64), index=True)
    cover_price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    thumbnail_image_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_image_url: Mapped[str | None] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    edition: Mapped[Edition] = relationship(back_populates="variants")


class Release(UuidMixin, TimestampMixin, Base):
    __tablename__ = "releases"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editions.id", ondelete="CASCADE"), index=True
    )
    region: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    release_date: Mapped[date | None] = mapped_column(Date)
    publisher: Mapped[str | None] = mapped_column(String(255))
    external_ids: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    edition: Mapped[Edition] = relationship(back_populates="releases")


class ExternalProviderId(UuidMixin, TimestampMixin, Base):
    __tablename__ = "external_provider_ids"
    __table_args__ = (
        UniqueConstraint("provider", "provider_item_id", name="uq_provider_provider_item_id"),
        Index("ix_external_entity", "entity_type", "entity_id"),
    )

    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    raw_url: Mapped[str | None] = mapped_column(String(1024))


class Organization(UuidMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(64), index=True)
    country: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Person(UuidMixin, TimestampMixin, Base):
    __tablename__ = "persons"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class EntityOrganization(UuidMixin, TimestampMixin, Base):
    __tablename__ = "entity_organizations"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "organization_id",
            "role",
            name="uq_entity_organization_role",
        ),
        Index("ix_entity_organizations_entity", "entity_type", "entity_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    organization: Mapped[Organization] = relationship()


class EntityPerson(UuidMixin, TimestampMixin, Base):
    __tablename__ = "entity_persons"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "person_id",
            "role",
            name="uq_entity_person_role",
        ),
        Index("ix_entity_persons_entity", "entity_type", "entity_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    person: Mapped[Person] = relationship()


class StoryArc(UuidMixin, TimestampMixin, Base):
    __tablename__ = "story_arcs"
    __table_args__ = (
        UniqueConstraint("name", "publisher", name="uq_story_arcs_name_publisher"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class StoryArcItem(UuidMixin, TimestampMixin, Base):
    __tablename__ = "story_arc_items"
    __table_args__ = (
        UniqueConstraint("story_arc_id", "item_id", name="uq_story_arc_item"),
        Index("ix_story_arc_items_story_arc", "story_arc_id"),
        Index("ix_story_arc_items_item", "item_id"),
    )

    story_arc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_arcs.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int | None] = mapped_column(Integer)

    story_arc: Mapped[StoryArc] = relationship()
    item: Mapped[Item] = relationship()


class Character(UuidMixin, TimestampMixin, Base):
    __tablename__ = "characters"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    aliases: Mapped[list[str] | None] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    first_appearance_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="SET NULL"), index=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class CharacterAppearance(UuidMixin, TimestampMixin, Base):
    __tablename__ = "character_appearances"
    __table_args__ = (
        UniqueConstraint("character_id", "item_id", name="uq_character_appearance"),
        Index("ix_character_appearances_character", "character_id"),
        Index("ix_character_appearances_item", "item_id"),
    )

    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    character: Mapped[Character] = relationship()
    item: Mapped[Item] = relationship()


class Tag(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("kind", "name", name="uq_tags_kind_name"),)

    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class EntityTag(UuidMixin, TimestampMixin, Base):
    __tablename__ = "entity_tags"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "tag_id", name="uq_entity_tag"),
        Index("ix_entity_tags_entity", "entity_type", "entity_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    tag: Mapped[Tag] = relationship()


class ImageAsset(UuidMixin, TimestampMixin, Base):
    __tablename__ = "image_assets"
    __table_args__ = (Index("ix_image_assets_entity", "entity_type", "entity_id"),)

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    image_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(512))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    provider: Mapped[str | None] = mapped_column(String(64), index=True)
    attribution: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    phash: Mapped[str | None] = mapped_column(String(128), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ImageCacheEntry(UuidMixin, TimestampMixin, Base):
    __tablename__ = "image_cache_entries"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_image_cache_object_key"),
        Index("ix_image_cache_provider_source", "provider", "source_url"),
        Index("ix_image_cache_last_accessed", "last_accessed_at"),
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_item_id: Mapped[str | None] = mapped_column(String(255), index=True)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    public_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrackingEntry(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tracking_entries"
    __table_args__ = (
        Index("ix_tracking_entries_user_item", "user_id", "item_id"),
        Index("ix_tracking_entries_user_status", "user_id", "status"),
        Index("ix_tracking_entries_owned_item", "owned_item_id"),
        Index("ix_tracking_entries_updated", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owned_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    edition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editions.id", ondelete="SET NULL"), index=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("variants.id", ondelete="SET NULL"), index=True
    )
    source_type: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    rating: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress_current: Mapped[int | None] = mapped_column(Integer)
    progress_total: Mapped[int | None] = mapped_column(Integer)
    times_completed: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    season_number: Mapped[int | None] = mapped_column(Integer)
    episode_number: Mapped[int | None] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    user: Mapped["User"] = relationship()
    item: Mapped[Item] = relationship()
    edition: Mapped[Edition | None] = relationship(foreign_keys=[edition_id])
    variant: Mapped[Variant | None] = relationship(foreign_keys=[variant_id])


class ProviderIngestJob(UuidMixin, TimestampMixin, Base):
    __tablename__ = "provider_ingest_jobs"
    __table_args__ = (
        Index("ix_provider_ingest_jobs_status_next_run", "status", "next_run_at"),
        Index("ix_provider_ingest_jobs_provider_item", "provider", "provider_item_id"),
    )

    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False, index=True
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)


class AdminAuditLog(UuidMixin, TimestampMixin, Base):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("ix_admin_audit_logs_action_created", "action", "created_at"),
        Index("ix_admin_audit_logs_entity", "entity_type", "entity_id"),
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class MetadataProposal(UuidMixin, TimestampMixin, Base):
    __tablename__ = "metadata_proposals"
    __table_args__ = (Index("ix_metadata_proposals_status_provider", "status", "provider"),)

    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False, index=True
    )
    provider_item_id: Mapped[str | None] = mapped_column(String(255), index=True)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)


class SeriesRelation(UuidMixin, TimestampMixin, Base):
    __tablename__ = "series_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_series_id",
            "target_series_id",
            "relation_type",
            name="uq_series_relations_source_target_type",
        ),
    )

    source_series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    target_series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[SeriesRelationType] = mapped_column(
        Enum(SeriesRelationType, name="series_relation_type", create_type=False),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    source_series: Mapped[Series] = relationship(
        foreign_keys=[source_series_id],
    )
    target_series: Mapped[Series] = relationship(
        foreign_keys=[target_series_id],
    )
