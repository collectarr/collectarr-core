"""Series groupings and memberships for flattened Book Catalog Items."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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
