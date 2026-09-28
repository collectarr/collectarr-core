from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin


class ImageAsset(UuidMixin, TimestampMixin, Base):
    __tablename__ = "image_assets"
    __table_args__ = (Index("ix_image_assets_catalog_item", "catalog_item_id"),)

    catalog_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("catalog_items.id", ondelete="CASCADE"),
        nullable=False,
    )
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

    details: Mapped[list[AdminAuditLogDetail]] = relationship(
        back_populates="audit_log",
        cascade="all, delete-orphan",
        order_by="AdminAuditLogDetail.path",
    )


class TypedScalarValueMixin:
    """Store a scalar value from an audit or duplicate review detail."""

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

    entities: Mapped[list[DuplicateReviewEntity]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="DuplicateReviewEntity.position",
    )
    details: Mapped[list[DuplicateReviewDetail]] = relationship(
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
