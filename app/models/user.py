import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin


class User(UuidMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    collections: Mapped[list["UserCollection"]] = relationship(back_populates="user")


class UserCollection(UuidMixin, TimestampMixin, Base):
    __tablename__ = "user_collections"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_collection_name"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Default")

    user: Mapped[User] = relationship(back_populates="collections")
    owned_items: Mapped[list["OwnedItem"]] = relationship(back_populates="collection")


class OwnedItem(UuidMixin, TimestampMixin, Base):
    __tablename__ = "owned_items"
    __table_args__ = (Index("ix_owned_user_updated", "user_id", "updated_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_collections.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), index=True
    )
    edition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editions.id", ondelete="SET NULL"), index=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("variants.id", ondelete="SET NULL"), index=True
    )
    condition: Mapped[str | None] = mapped_column(String(64))
    grade: Mapped[str | None] = mapped_column(String(64))
    acquired_from: Mapped[str | None] = mapped_column(String(255))
    purchase_price_cents: Mapped[int | None]
    currency: Mapped[str | None] = mapped_column(String(3))
    personal_notes: Mapped[str | None] = mapped_column(Text)
    client_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    collection: Mapped[UserCollection] = relationship(back_populates="owned_items")

    def mark_deleted(self) -> None:
        self.deleted_at = datetime.now(UTC)


class WishlistItem(UuidMixin, TimestampMixin, Base):
    __tablename__ = "wishlist_items"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="RESTRICT"), index=True
    )
    edition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editions.id", ondelete="SET NULL"), index=True
    )
    priority: Mapped[int | None]
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Note(UuidMixin, TimestampMixin, Base):
    __tablename__ = "notes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    owned_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("owned_items.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)


class Tag(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_tag_name"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)


class OwnedItemTag(Base):
    __tablename__ = "owned_item_tags"

    owned_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("owned_items.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
