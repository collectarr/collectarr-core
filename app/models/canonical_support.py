import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    and_,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import (
    Base,
    ItemKind,
    SeriesRelationType,
    TimestampMixin,
    UuidMixin,
)

if TYPE_CHECKING:
    from app.models import ComicSeries, MangaSeries


class Organization(UuidMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(64), index=True)
    country: Mapped[str | None] = mapped_column(String(64), index=True)
    parent_publisher: Mapped[str | None] = mapped_column(String(255), index=True)


class Person(UuidMixin, TimestampMixin, Base):
    __tablename__ = "persons"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_name: Mapped[str | None] = mapped_column(String(255), index=True)
    biography: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))


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
    start_date_parts: Mapped[str | None] = mapped_column(String(64))
    end_date: Mapped[date | None] = mapped_column(Date)
    end_date_parts: Mapped[str | None] = mapped_column(String(64))


class StoryArcItem(UuidMixin, TimestampMixin, Base):
    __tablename__ = "story_arc_items"
    __table_args__ = (
        UniqueConstraint("story_arc_id", "entity_type", "entity_id", name="uq_story_arc_item"),
        Index("ix_story_arc_items_story_arc", "story_arc_id"),
        Index("ix_story_arc_items_entity", "entity_type", "entity_id"),
    )

    story_arc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_arcs.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    ordinal: Mapped[int | None] = mapped_column(Integer)

    story_arc: Mapped["StoryArc"] = relationship()


class Character(UuidMixin, TimestampMixin, Base):
    __tablename__ = "characters"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    canonical_name: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    first_appearance_entity_type: Mapped[str | None] = mapped_column(String(64), index=True)
    first_appearance_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )

    alias_entries: Mapped[list["EntityAlias"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityAlias.entity_id) == Character.id,
            EntityAlias.entity_type == "character",
        ),
        order_by="EntityAlias.position",
        cascade="all, delete-orphan",
    )
class CharacterAppearance(UuidMixin, TimestampMixin, Base):
    __tablename__ = "character_appearances"
    __table_args__ = (
        UniqueConstraint("character_id", "entity_type", "entity_id", name="uq_character_appearance"),
        Index("ix_character_appearances_character", "character_id"),
        Index("ix_character_appearances_entity", "entity_type", "entity_id"),
    )

    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    character: Mapped["Character"] = relationship()


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
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    phash: Mapped[str | None] = mapped_column(String(128), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ImageCacheEntry(UuidMixin, TimestampMixin, Base):
    __tablename__ = "image_cache_entries"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_image_cache_object_key"),
        Index("ix_image_cache_source_url", "source_url"),
        Index("ix_image_cache_last_accessed", "last_accessed_at"),
    )

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

    details: Mapped[list["AdminAuditLogDetail"]] = relationship(
        back_populates="audit_log",
        cascade="all, delete-orphan",
        order_by="AdminAuditLogDetail.path",
    )


class TypedScalarValueMixin:
    """Concrete storage for one scalar value in a structured workflow payload."""

    value_type: Mapped[str] = mapped_column(String(16), nullable=False)
    string_value: Mapped[str | None] = mapped_column(Text)
    integer_value: Mapped[int | None] = mapped_column(BigInteger)
    decimal_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
    date_value: Mapped[date | None] = mapped_column(Date)
    date_value_parts: Mapped[str | None] = mapped_column(String(64))
    datetime_value: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uuid_value: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class AdminAuditLogDetail(UuidMixin, TimestampMixin, TypedScalarValueMixin, Base):
    __tablename__ = "admin_audit_log_details"
    __table_args__ = (
        UniqueConstraint("audit_log_id", "path", name="uq_admin_audit_log_details_path"),
        Index("ix_admin_audit_log_details_audit_log", "audit_log_id"),
    )

    audit_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_audit_logs.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)

    audit_log: Mapped[AdminAuditLog] = relationship(back_populates="details")


class DuplicateReview(UuidMixin, TimestampMixin, Base):
    __tablename__ = "duplicate_reviews"
    __table_args__ = (
        UniqueConstraint("action", "ignore_token", name="uq_duplicate_reviews_action_ignore_token"),
        Index("ix_duplicate_reviews_action_created", "action", "created_at"),
        Index("ix_duplicate_reviews_entity", "entity_type", "entity_id"),
        Index("ix_duplicate_reviews_ignore_token", "ignore_token"),
    )

    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    ignore_token: Mapped[str | None] = mapped_column(String(128))
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    duplicate_score: Mapped[int | None] = mapped_column(Integer)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), index=True)
    note: Mapped[str | None] = mapped_column(Text)

    entities: Mapped[list["DuplicateReviewEntity"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="DuplicateReviewEntity.position",
    )
    details: Mapped[list["DuplicateReviewDetail"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="DuplicateReviewDetail.path",
    )


class DuplicateReviewEntity(UuidMixin, TimestampMixin, Base):
    __tablename__ = "duplicate_review_entities"
    __table_args__ = (
        UniqueConstraint("review_id", "role", "entity_id", name="uq_duplicate_review_entities"),
        Index("ix_duplicate_review_entities_review_position", "review_id", "position"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("duplicate_reviews.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    review: Mapped[DuplicateReview] = relationship(back_populates="entities")


class DuplicateReviewDetail(UuidMixin, TimestampMixin, TypedScalarValueMixin, Base):
    __tablename__ = "duplicate_review_details"
    __table_args__ = (
        UniqueConstraint("review_id", "path", name="uq_duplicate_review_details_path"),
        Index("ix_duplicate_review_details_review", "review_id"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("duplicate_reviews.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)

    review: Mapped[DuplicateReview] = relationship(back_populates="details")


class CanonicalCorrectionProposal(UuidMixin, TimestampMixin, Base):
    """Provider-independent correction proposal for one canonical entity."""

    __tablename__ = "canonical_correction_proposals"
    __table_args__ = (
        CheckConstraint(
            "base_revision IS NOT NULL OR base_hash IS NOT NULL",
            name="ck_canonical_correction_proposals_base_present",
        ),
        Index(
            "ix_canonical_correction_proposals_target",
            "kind",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_canonical_correction_proposals_status_created",
            "status",
            "created_at",
        ),
    )

    kind: Mapped[ItemKind] = mapped_column(
        Enum(ItemKind, name="item_kind", create_type=False), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    base_revision: Mapped[str | None] = mapped_column(String(128))
    base_hash: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)

    values: Mapped[list["CanonicalCorrectionProposalValue"]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        order_by="CanonicalCorrectionProposalValue.path",
    )


class CanonicalCorrectionProposalValue(
    UuidMixin, TimestampMixin, TypedScalarValueMixin, Base
):
    __tablename__ = "canonical_correction_proposal_values"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id",
            "path",
            name="uq_canonical_correction_proposal_values_path",
        ),
        Index(
            "ix_canonical_correction_proposal_values_proposal",
            "proposal_id",
        ),
    )

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_correction_proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)

    proposal: Mapped[CanonicalCorrectionProposal] = relationship(back_populates="values")


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

    source_series: Mapped["ComicSeries"] = relationship(
        foreign_keys=[source_series_id],
    )
    target_series: Mapped["ComicSeries"] = relationship(
        foreign_keys=[target_series_id],
    )
