from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, Integer, String, Text, and_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin
from app.models.canonical_manga import MangaWork
from app.models.canonical_support import Person


class MangaEdition(UuidMixin, TimestampMixin, Base):
    """Canonical Manga release/edition under a Volume work."""

    __tablename__ = "manga_editions"
    __table_args__ = (
        Index("ix_manga_editions_work_publication", "work_id", "publication_date"),
        Index("ix_manga_editions_work_isbn13", "work_id", "isbn13"),
        Index("ix_manga_editions_work_barcode", "work_id", "barcode"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_title: Mapped[str | None] = mapped_column(String(255))
    edition_statement: Mapped[str | None] = mapped_column(String(255))
    format: Mapped[str | None] = mapped_column(String(100), index=True)
    binding: Mapped[str | None] = mapped_column(String(100), index=True)
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    publication_date_parts: Mapped[str | None] = mapped_column(String(64))
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    imprint: Mapped[str | None] = mapped_column(String(255), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    country: Mapped[str | None] = mapped_column(String(32), index=True)
    isbn10: Mapped[str | None] = mapped_column(String(32), index=True)
    isbn13: Mapped[str | None] = mapped_column(String(32), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)

    work: Mapped[MangaWork] = relationship(back_populates="editions")
    contributions: Mapped[list["MangaEditionContribution"]] = relationship(
        back_populates="edition", cascade="all, delete-orphan"
    )
    identifiers: Mapped[list["MangaEditionIdentifier"]] = relationship(
        back_populates="edition", cascade="all, delete-orphan"
    )


class MangaEditionContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_edition_contributions"
    __table_args__ = (
        Index("ix_manga_edition_contributions_edition_role", "edition_id", "role", "sequence"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_id: Mapped[str | None] = mapped_column(String(64), index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)

    edition: Mapped[MangaEdition] = relationship(back_populates="contributions")
    person: Mapped[Person] = relationship()


class MangaEditionIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_edition_identifiers"
    __table_args__ = (
        Index("ix_manga_edition_identifiers_edition_type_value", "edition_id", "identifier_type", "normalized_value"),
        Index("ix_manga_edition_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    edition: Mapped[MangaEdition] = relationship(back_populates="identifiers")
