from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import Base, ExternalProvider, TimestampMixin, UuidMixin
from app.models.canonical_anime import AnimeEpisode, AnimeSeries
from app.models.canonical_support import ExternalProviderId, Person


class AnimeRelease(UuidMixin, TimestampMixin, Base):
    """Canonical physical/digital release under an Anime Work."""

    __tablename__ = "anime_releases"
    __table_args__ = (
        Index("ix_anime_releases_work_release_date", "work_id", "release_date"),
        Index("ix_anime_releases_work_barcode", "work_id", "barcode"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    media_count: Mapped[int | None] = mapped_column(Integer)
    format: Mapped[str | None] = mapped_column(String(64), index=True)
    region_code: Mapped[str | None] = mapped_column(String(32), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    release_date_parts: Mapped[str | None] = mapped_column(String(64))
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    distributor: Mapped[str | None] = mapped_column(String(255), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100), index=True)
    packaging: Mapped[str | None] = mapped_column(String(64))
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    language_audio: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    language_subtitles: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))

    work: Mapped[AnimeSeries] = relationship(back_populates="releases")
    media: Mapped[list["AnimeReleaseMedia"]] = relationship(
        back_populates="release", cascade="all, delete-orphan"
    )
    episode_mappings: Mapped[list["AnimeReleaseEpisodeMap"]] = relationship(
        back_populates="release", cascade="all, delete-orphan"
    )
    contributions: Mapped[list["AnimeReleaseContribution"]] = relationship(
        back_populates="release", cascade="all, delete-orphan"
    )
    identifiers: Mapped[list["AnimeReleaseIdentifier"]] = relationship(
        back_populates="release", cascade="all, delete-orphan"
    )
    provider_links: Mapped[list[ExternalProviderId]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == AnimeRelease.id,
            ExternalProviderId.entity_type == "anime_release",
        ),
        viewonly=True,
    )


class AnimeReleaseMedia(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_release_media"
    __table_args__ = (
        UniqueConstraint("release_id", "media_number", name="uq_anime_release_media_release_number"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_number: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    episode_count: Mapped[int | None] = mapped_column(Integer)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    region_code: Mapped[str | None] = mapped_column(String(32))
    encoding: Mapped[str | None] = mapped_column(String(64))
    aspect_ratio: Mapped[str | None] = mapped_column(String(16))
    audio_tracks: Mapped[str | None] = mapped_column(String(500))
    subtitles: Mapped[str | None] = mapped_column(String(500))
    resolution: Mapped[str | None] = mapped_column(String(16))
    hdr_format: Mapped[str | None] = mapped_column(String(64))

    release: Mapped[AnimeRelease] = relationship(back_populates="media")
    episode_mappings: Mapped[list["AnimeReleaseEpisodeMap"]] = relationship(
        back_populates="media", cascade="all, delete-orphan"
    )


class AnimeReleaseEpisodeMap(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_release_episode_map"
    __table_args__ = (
        UniqueConstraint("release_id", "media_id", "episode_id", name="uq_anime_release_episode_map"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_release_media.id", ondelete="CASCADE"), nullable=False, index=True
    )
    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    disc_number: Mapped[int | None] = mapped_column(Integer)
    sequence_number: Mapped[int | None] = mapped_column(Integer)

    release: Mapped[AnimeRelease] = relationship(back_populates="episode_mappings")
    media: Mapped[AnimeReleaseMedia] = relationship(back_populates="episode_mappings")
    episode: Mapped[AnimeEpisode] = relationship(back_populates="release_mappings")


class AnimeReleaseContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_release_contributions"
    __table_args__ = (Index("ix_anime_release_contributions_release_role", "release_id", "role", "sequence"),)

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_id: Mapped[str | None] = mapped_column(String(64), index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)

    release: Mapped[AnimeRelease] = relationship(back_populates="contributions")
    person: Mapped[Person] = relationship()


class AnimeReleaseIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_release_identifiers"
    __table_args__ = (
        Index("ix_anime_release_identifiers_release_type_value", "release_id", "identifier_type", "normalized_value"),
        Index("ix_anime_release_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False), index=True
    )

    release: Mapped[AnimeRelease] = relationship(back_populates="identifiers")
