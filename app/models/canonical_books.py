from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import (
    Base,
    ExternalProvider,
    TimestampMixin,
    UuidMixin,
)
from app.models.canonical_support import (  # noqa: F401
    AdminAuditLog,
    AdminReleaseMediaMappingRule,
    Character,
    CharacterAppearance,
    ComicSeriesRelation,
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
    SeriesRelation,
    StoryArc,
    StoryArcItem,
    Tag,
)


class BookWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_works"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(16), index=True)
    original_publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    first_publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    editions: Mapped[list["BookEdition"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["BookContribution"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    series_memberships: Mapped[list["BookSeriesMembership"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )


class BookSeries(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_series"

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

    works: Mapped[list["BookSeriesMembership"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == BookSeries.id,
            ExternalProviderId.entity_type == "book_series",
        ),
        viewonly=True,
    )


class BookEdition(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_editions"
    __table_args__ = (
        Index("ix_book_editions_work_publication", "work_id", "publication_date"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_title: Mapped[str | None] = mapped_column(String(255))
    edition_statement: Mapped[str | None] = mapped_column(String(255))
    format: Mapped[str | None] = mapped_column(String(100), index=True)
    binding: Mapped[str | None] = mapped_column(String(100), index=True)
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    imprint: Mapped[str | None] = mapped_column(String(255), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    audio_length_minutes: Mapped[int | None] = mapped_column(Integer)
    age_rating: Mapped[str | None] = mapped_column(String(64), index=True)
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BookWork] = relationship(back_populates="editions")
    printings: Mapped[list["BookPrinting"]] = relationship(
        back_populates="edition",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["BookContribution"]] = relationship(
        back_populates="edition",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["BookIdentifier"]] = relationship(
        back_populates="edition",
        cascade="all, delete-orphan",
    )


class BookPrinting(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_printings"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    printing_number: Mapped[int | None] = mapped_column(Integer, index=True)
    printing_statement: Mapped[str | None] = mapped_column(String(255))
    print_run: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    edition: Mapped[BookEdition] = relationship(back_populates="printings")


class BookContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_contributions"
    __table_args__ = (
        CheckConstraint(
            "((work_id IS NOT NULL AND edition_id IS NULL) OR (work_id IS NULL AND edition_id IS NOT NULL))",
            name="ck_book_contributions_work_xor_edition",
        ),
        Index(
            "ix_book_contributions_work_role_sequence",
            "work_id",
            "role",
            "sequence",
        ),
        Index(
            "ix_book_contributions_edition_role_sequence",
            "edition_id",
            "role",
            "sequence",
        ),
    )

    work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_works.id", ondelete="CASCADE"), index=True
    )
    edition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_editions.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BookWork | None] = relationship(back_populates="contributions")
    edition: Mapped[BookEdition | None] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class BookIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "edition_id",
            "identifier_type",
            "normalized_value",
            name="uq_book_identifiers_edition_type_normalized",
        ),
        Index("ix_book_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    edition: Mapped[BookEdition] = relationship(back_populates="identifiers")


class BookSeriesMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_series_memberships"
    __table_args__ = (
        UniqueConstraint("work_id", "series_id", name="uq_book_series_memberships_work_series"),
        Index("ix_book_series_memberships_series_sequence", "series_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[float | None] = mapped_column(Float)
    display_number: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BookWork] = relationship(back_populates="series_memberships")
    series: Mapped[BookSeries] = relationship(back_populates="works")
