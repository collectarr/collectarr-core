from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class AnimeSeries(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_series"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(16))
    original_air_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    anime_type: Mapped[str | None] = mapped_column(String(64), index=True)
    episode_count: Mapped[int | None]
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    episodes: Mapped[list["AnimeEpisode"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )
    contributions: Mapped[list["AnimeContribution"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )
    identifiers: Mapped[list["AnimeIdentifier"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )
    character_appearances: Mapped[list["AnimeCharacterAppearance"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )


class AnimeEpisode(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_episodes"

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    episode_number: Mapped[int | None]
    episode_title: Mapped[str | None] = mapped_column(String(255))
    air_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(255))
    runtime_minutes: Mapped[int | None]
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[AnimeSeries] = relationship(back_populates="episodes")


class AnimeContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_contributions"
    __table_args__ = (
        CheckConstraint(
            "(series_id IS NOT NULL AND episode_id IS NULL) OR (series_id IS NULL AND episode_id IS NOT NULL)",
            name="ck_anime_contributions_xor_series_episode",
        ),
    )

    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_series.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_episodes.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[AnimeSeries | None] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class AnimeIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "identifier_type",
            "normalized_value",
            name="uq_anime_identifiers_series_type_normalized",
        ),
        Index("ix_anime_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_series.id", ondelete="CASCADE"), nullable=False, index=True
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

    series: Mapped[AnimeSeries] = relationship(back_populates="identifiers")


class AnimeCharacterAppearance(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_character_appearances"
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "character_id",
            "role",
            name="uq_anime_character_appearances_series_character_role",
        ),
        Index("ix_anime_character_appearances_series_role", "series_id", "role"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="featured", index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[AnimeSeries] = relationship(back_populates="character_appearances")
    character: Mapped["Character"] = relationship()
