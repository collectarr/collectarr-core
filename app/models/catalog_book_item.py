"""Flattened Book Catalog Items and contained edition details."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin


class BookItem(UuidMixin, TimestampMixin, Base):
    """One concrete book edition, without an editable Work parent."""

    __tablename__ = "book_items"
    __table_args__ = (
        Index("ix_book_items_title", "title"),
        Index(
            "ix_book_items_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_book_items_sort_key", "sort_key"),
        Index(
            "ix_book_items_sort_key_trgm",
            "sort_key",
            postgresql_using="gin",
            postgresql_ops={"sort_key": "gin_trgm_ops"},
        ),
        Index("ix_book_items_barcode", "barcode"),
        Index("ix_book_items_catalog_number", "catalog_number"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_key: Mapped[str | None] = mapped_column(String(255))
    barcode: Mapped[str | None] = mapped_column(String(100))
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}

    printings: Mapped[list["BookItemPrinting"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="BookItemPrinting.printing_number",
    )
    credits: Mapped[list["BookItemCredit"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="BookItemCredit.sequence",
    )
    identifiers: Mapped[list["BookItemIdentifier"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="BookItemIdentifier.identifier_type",
    )
    series_memberships: Mapped[list["BookItemSeriesMembership"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )


class BookItemPrinting(UuidMixin, TimestampMixin, Base):
    """A contained printing record for one concrete edition."""

    __tablename__ = "book_item_printings"
    __table_args__ = (Index("ix_book_item_printings_item", "book_item_id"),)

    book_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    printing_number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(255))
    release_date: Mapped[Any | None] = mapped_column(JSONB)
    publisher: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(16))
    isbn: Mapped[str | None] = mapped_column(String(32))

    item: Mapped[BookItem] = relationship(back_populates="printings")


class BookItemCredit(UuidMixin, TimestampMixin, Base):
    """A creator or contributor attached to one flattened book item."""

    __tablename__ = "book_item_credits"
    __table_args__ = (
        Index("ix_book_item_credits_item_role", "book_item_id", "credit_type", "sequence"),
    )

    book_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    credit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(64))
    role_id: Mapped[str | None] = mapped_column(String(64))
    sequence: Mapped[int | None] = mapped_column(Integer)

    item: Mapped[BookItem] = relationship(back_populates="credits")


class BookItemIdentifier(UuidMixin, TimestampMixin, Base):
    """An edition identifier such as an ISBN or a catalog number."""

    __tablename__ = "book_item_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "book_item_id",
            "identifier_type",
            "normalized_value",
            name="uq_book_item_identifier_normalized",
        ),
        Index("ix_book_item_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    book_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    item: Mapped[BookItem] = relationship(back_populates="identifiers")
