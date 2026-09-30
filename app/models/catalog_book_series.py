"""Series groupings and memberships for flattened Book Catalog Items."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin


class BookSeries(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_series"
    __table_args__ = (
        Index("ix_book_series_title", "title"),
        Index("ix_book_series_slug", "slug"),
        Index("ix_book_series_status", "status"),
        Index("ix_book_series_language", "language"),
        Index("ix_book_series_country", "country"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    original_title: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    start_date_parts: Mapped[str | None] = mapped_column(String(64))
    end_date: Mapped[date | None] = mapped_column(Date)
    end_date_parts: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(16))
    country: Mapped[str | None] = mapped_column(String(64))

    memberships: Mapped[list["BookItemSeriesMembership"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )


class BookItemSeriesMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_item_series_memberships"
    __table_args__ = (
        UniqueConstraint(
            "book_item_id",
            "series_id",
            name="uq_book_item_series_memberships_item_series",
        ),
        Index("ix_book_item_series_memberships_series_sequence", "series_id", "sequence"),
    )

    book_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[float | None] = mapped_column(Float)
    display_number: Mapped[str | None] = mapped_column(String(64))

    item: Mapped["BookItem"] = relationship(back_populates="series_memberships")
    series: Mapped[BookSeries] = relationship(back_populates="memberships")
