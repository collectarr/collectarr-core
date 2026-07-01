import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

from app.models.base import (
    Base,
    ExternalProvider,
    ItemKind,
    SeriesRelationType,
    TimestampMixin,
    UuidMixin,
)

if TYPE_CHECKING:
    from app.models import ComicSeries, MangaSeries


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
    site_url: Mapped[str | None] = mapped_column(String(1024))
    api_url: Mapped[str | None] = mapped_column(String(1024))


class ProviderPayloadSnapshot(UuidMixin, TimestampMixin, Base):
    __tablename__ = "provider_payload_snapshots"
    __table_args__ = (
        Index("ix_provider_payload_snapshots_entity", "entity_type", "entity_id"),
        Index("ix_provider_payload_snapshots_provider_item", "provider", "provider_item_id"),
    )

    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False, index=True
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    normalized_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Organization(UuidMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(64), index=True)
    country: Mapped[str | None] = mapped_column(String(64), index=True)
    parent_publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Person(UuidMixin, TimestampMixin, Base):
    __tablename__ = "persons"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    api_detail_url: Mapped[str | None] = mapped_column(String(1024))
    site_detail_url: Mapped[str | None] = mapped_column(String(1024))
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
        Index("ix_entity_organizations_organization", "organization_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    organization: Mapped["Organization"] = relationship()


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
        Index("ix_entity_persons_person", "person_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    person: Mapped["Person"] = relationship()


class EntityAlias(UuidMixin, TimestampMixin, Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "normalized_alias",
            name="uq_entity_aliases_entity_normalized_alias",
        ),
        Index("ix_entity_aliases_entity_position", "entity_type", "entity_id", "position"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

class EntityLink(UuidMixin, TimestampMixin, Base):
    __tablename__ = "entity_links"
    __table_args__ = (
        CheckConstraint(
            "link_type IN ('trailer', 'external')",
            name="ck_entity_links_link_type_valid",
        ),
        Index("ix_entity_links_entity_type_position", "entity_type", "entity_id", "link_type", "position"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    site: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    kind: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

class StoryArc(UuidMixin, TimestampMixin, Base):
    __tablename__ = "story_arcs"
    __table_args__ = (UniqueConstraint("name", "publisher", name="uq_story_arcs_name_publisher"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    api_detail_url: Mapped[str | None] = mapped_column(String(1024))
    site_detail_url: Mapped[str | None] = mapped_column(String(1024))
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

    story_arc: Mapped["StoryArc"] = relationship()
    item: Mapped["Item"] = relationship(back_populates="story_arc_items")


class Character(UuidMixin, TimestampMixin, Base):
    __tablename__ = "characters"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    canonical_name: Mapped[str | None] = mapped_column(String(255), index=True)
    aliases: Mapped[list[str] | None] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    api_detail_url: Mapped[str | None] = mapped_column(String(1024))
    site_detail_url: Mapped[str | None] = mapped_column(String(1024))
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

    character: Mapped["Character"] = relationship()
    item: Mapped["Item"] = relationship(back_populates="character_appearances")


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
        Index("ix_entity_tags_tag", "tag_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    tag: Mapped["Tag"] = relationship()


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


class AdminReleaseMediaMappingRule(UuidMixin, TimestampMixin, Base):
    __tablename__ = "admin_release_media_mapping_rules"
    __table_args__ = (
        Index(
            "ix_admin_release_media_mapping_rules_lookup",
            "release_type",
            "provider",
            "is_active",
            "priority",
        ),
    )

    provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        nullable=True,
        index=True,
    )
    release_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_kind: Mapped[ItemKind] = mapped_column(
        Enum(ItemKind, name="item_kind", create_type=False), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class MangaSeriesRelation(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_series_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_series_id",
            "target_series_id",
            "relation_type",
            name="uq_manga_series_relations_source_target_type",
        ),
    )

    source_series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_series.id", ondelete="CASCADE"), index=True
    )
    target_series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_series.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[SeriesRelationType] = mapped_column(
        Enum(SeriesRelationType, name="series_relation_type", create_type=False),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    start_year: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(64), index=True)
    provider_id: Mapped[str | None] = mapped_column(String(255), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    source_series: Mapped["MangaSeries"] = relationship(
        foreign_keys=[source_series_id],
    )
    target_series: Mapped["MangaSeries"] = relationship(
        foreign_keys=[target_series_id],
    )


class ComicSeriesRelation(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_series_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_series_id",
            "target_series_id",
            "relation_type",
            name="uq_comic_series_relations_source_target_type",
        ),
    )

    source_series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_series.id", ondelete="CASCADE"), index=True
    )
    target_series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_series.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[SeriesRelationType] = mapped_column(
        Enum(SeriesRelationType, name="series_relation_type", create_type=False),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    start_year: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(64), index=True)
    provider_id: Mapped[str | None] = mapped_column(String(255), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    source_series: Mapped["ComicSeries"] = relationship(
        foreign_keys=[source_series_id],
    )
    target_series: Mapped["ComicSeries"] = relationship(
        foreign_keys=[target_series_id],
    )
