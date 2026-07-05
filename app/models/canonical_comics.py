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


class ComicSeries(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_series"

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

    works: Mapped[list["ComicSeriesMembership"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == ComicSeries.id,
            ExternalProviderId.entity_type == "comic_series",
        ),
        viewonly=True,
    )


class ComicWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_works"

    volume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_volumes.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(16), index=True)
    first_publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    expected_issue_count: Mapped[int | None] = mapped_column(Integer)
    missing_issue_count: Mapped[int | None] = mapped_column(Integer)
    missing_issue_numbers: Mapped[list[int] | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    volume: Mapped["ComicVolume | None"] = relationship(back_populates="works")
    issues: Mapped[list["ComicIssue"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["ComicContribution"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    series_memberships: Mapped[list["ComicSeriesMembership"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )


class ComicVolume(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_volumes"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    original_title: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    start_year: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    country: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    works: Mapped[list["ComicWork"]] = relationship(back_populates="volume")
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == ComicVolume.id,
            ExternalProviderId.entity_type == "comic_volume",
        ),
        viewonly=True,
    )


class ComicIssue(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_issues"
    __table_args__ = (
        Index("ix_comic_issues_work_issue_number", "work_id", "issue_number"),
        Index("ix_comic_issues_work_publication", "work_id", "publication_date"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issue_number: Mapped[str | None] = mapped_column(String(64), index=True)
    display_title: Mapped[str | None] = mapped_column(String(255))
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    imprint: Mapped[str | None] = mapped_column(String(255), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    cover_price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(8))
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    key_comic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    key_reason: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[ComicWork] = relationship(back_populates="issues")
    contributions: Mapped[list["ComicContribution"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["ComicIdentifier"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    story_arc_memberships: Mapped[list["ComicStoryArcMembership"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    character_appearances: Mapped[list["ComicCharacterAppearance"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )


class ComicContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_contributions"
    __table_args__ = (
        CheckConstraint(
            "((work_id IS NOT NULL AND issue_id IS NULL) OR (work_id IS NULL AND issue_id IS NOT NULL))",
            name="ck_comic_contributions_work_xor_issue",
        ),
        Index("ix_comic_contributions_work_role_sequence", "work_id", "role", "sequence"),
        Index("ix_comic_contributions_issue_role_sequence", "issue_id", "role", "sequence"),
    )

    work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_works.id", ondelete="CASCADE"), index=True
    )
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_issues.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_id: Mapped[str | None] = mapped_column(String(64), index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[ComicWork | None] = relationship(back_populates="contributions")
    issue: Mapped[ComicIssue | None] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class ComicIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "issue_id",
            "identifier_type",
            "normalized_value",
            name="uq_comic_identifiers_issue_type_normalized",
        ),
        Index("ix_comic_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_issues.id", ondelete="CASCADE"), nullable=False, index=True
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

    issue: Mapped[ComicIssue] = relationship(back_populates="identifiers")


class ComicStoryArcMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_story_arc_memberships"
    __table_args__ = (
        UniqueConstraint("issue_id", "story_arc_id", name="uq_comic_story_arc_memberships_issue_arc"),
        Index("ix_comic_story_arc_memberships_issue_ordinal", "issue_id", "ordinal"),
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    story_arc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_arcs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    issue: Mapped[ComicIssue] = relationship(back_populates="story_arc_memberships")
    story_arc: Mapped["StoryArc"] = relationship()


class ComicCharacterAppearance(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_character_appearances"
    __table_args__ = (
        UniqueConstraint(
            "issue_id",
            "character_id",
            "role",
            name="uq_comic_character_appearances_issue_character_role",
        ),
        Index("ix_comic_character_appearances_issue_role", "issue_id", "role"),
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="featured", index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    issue: Mapped[ComicIssue] = relationship(back_populates="character_appearances")
    character: Mapped["Character"] = relationship()


class ComicSeriesMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_series_memberships"
    __table_args__ = (
        UniqueConstraint("work_id", "series_id", name="uq_comic_series_memberships_work_series"),
        Index("ix_comic_series_memberships_series_sequence", "series_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[float | None] = mapped_column(Float)
    display_number: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[ComicWork] = relationship(back_populates="series_memberships")
    series: Mapped[ComicSeries] = relationship(back_populates="works")


class ComicCharacter(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_characters"
    __table_args__ = (
        Index("ix_comic_characters_name", "name"),
        Index("ix_comic_characters_sort_name", "sort_name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_name: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(1024))
    external_ids: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
