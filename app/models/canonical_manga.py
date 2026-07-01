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
    StoryArc,
    StoryArcItem,
    Tag,
)


class MangaWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_works"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(16))
    original_publication_date: Mapped[date | None] = mapped_column(Date)
    first_publication_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    chapters: Mapped[list["MangaChapter"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )
    contributions: Mapped[list["MangaContribution"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )
    identifiers: Mapped[list["MangaIdentifier"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )
    character_appearances: Mapped[list["MangaCharacterAppearance"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )
    series_memberships: Mapped[list["MangaSeriesMembership"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )


class MangaChapter(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_chapters"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_number: Mapped[float | None] = mapped_column(Float)
    chapter_title: Mapped[str | None] = mapped_column(String(255))
    publication_date: Mapped[date | None] = mapped_column(Date)
    page_count: Mapped[int | None]
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[MangaWork] = relationship(back_populates="chapters")


class MangaContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_contributions"
    __table_args__ = (
        CheckConstraint(
            "(work_id IS NOT NULL AND chapter_id IS NULL) OR (work_id IS NULL AND chapter_id IS NOT NULL)",
            name="ck_manga_contributions_xor_work_chapter",
        ),
    )

    work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), index=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_chapters.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[MangaWork | None] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class MangaIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "work_id",
            "identifier_type",
            "normalized_value",
            name="uq_manga_identifiers_work_type_normalized",
        ),
        Index("ix_manga_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), nullable=False, index=True
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

    work: Mapped[MangaWork] = relationship(back_populates="identifiers")


class MangaCharacterAppearance(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_character_appearances"
    __table_args__ = (
        UniqueConstraint(
            "work_id",
            "character_id",
            "role",
            name="uq_manga_character_appearances_work_character_role",
        ),
        Index("ix_manga_character_appearances_work_role", "work_id", "role"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="featured", index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[MangaWork] = relationship(back_populates="character_appearances")
    character: Mapped["Character"] = relationship()


class MangaSeries(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_series"

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

    works: Mapped[list["MangaSeriesMembership"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == MangaSeries.id,
            ExternalProviderId.entity_type == "manga_series",
        ),
        viewonly=True,
    )


class MangaSeriesMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_series_memberships"
    __table_args__ = (
        UniqueConstraint("work_id", "series_id", name="uq_manga_series_memberships_work_series"),
        Index("ix_manga_series_memberships_series_sequence", "series_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[float | None] = mapped_column(Float)
    display_number: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[MangaWork] = relationship(back_populates="series_memberships")
    series: Mapped[MangaSeries] = relationship(back_populates="works")
