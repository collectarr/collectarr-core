from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ExternalProvider, TimestampMixin, UuidMixin


class MusicReleaseGroup(UuidMixin, TimestampMixin, Base):
    """MusicBrainz release-group: the conceptual album/work."""

    __tablename__ = "music_release_groups"
    __table_args__ = (
        Index("idx_music_release_groups_title", "title"),
        Index("idx_music_release_groups_created_at", "created_at"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    original_title: Mapped[str | None] = mapped_column(String(255))
    synopsis: Mapped[str | None] = mapped_column(Text)
    artist: Mapped[str | None] = mapped_column(String(500))
    original_release_date: Mapped[date | None] = mapped_column(Date)
    recording_date: Mapped[date | None] = mapped_column(Date)
    studio: Mapped[str | None] = mapped_column(String(255))
    is_live: Mapped[bool | None] = mapped_column(Boolean)
    genres: Mapped[list[str] | None] = mapped_column(JSONB)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    releases: Mapped[list["MusicRelease"]] = relationship(
        back_populates="release_group",
        cascade="all, delete-orphan",
    )


class MusicRelease(UuidMixin, TimestampMixin, Base):
    """Concrete pressing/edition of a release group."""

    __tablename__ = "music_releases"
    __table_args__ = (
        Index("idx_music_releases_release_group_id", "release_group_id"),
        Index("idx_music_releases_barcode", "barcode"),
        Index("idx_music_releases_created_at", "created_at"),
    )

    release_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("music_release_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    release_type: Mapped[str | None] = mapped_column(String(64))
    release_status: Mapped[str | None] = mapped_column(String(50))
    release_date: Mapped[date | None] = mapped_column(Date)
    publisher: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(2))
    language: Mapped[str | None] = mapped_column(String(2))
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    upc: Mapped[str | None] = mapped_column(String(100), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    packaging: Mapped[str | None] = mapped_column(String(100))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release_group: Mapped[MusicReleaseGroup] = relationship(back_populates="releases")
    mediums: Mapped[list["MusicMedium"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["MusicReleaseContribution"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["MusicReleaseIdentifier"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )


class MusicMedium(UuidMixin, TimestampMixin, Base):
    """Physical or digital medium inside a concrete release."""

    __tablename__ = "music_mediums"
    __table_args__ = (
        UniqueConstraint("release_id", "medium_number", name="unique_music_medium"),
        Index("idx_music_mediums_release_id", "release_id"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("music_releases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    medium_number: Mapped[int] = mapped_column(Integer, nullable=False)
    medium_type: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))
    track_count: Mapped[int | None] = mapped_column(Integer)
    expected_track_count: Mapped[int | None] = mapped_column(Integer)
    missing_track_count: Mapped[int | None] = mapped_column(Integer)
    missing_track_positions: Mapped[list[str] | None] = mapped_column(JSONB)
    toc: Mapped[str | None] = mapped_column(Text)
    cddb_id: Mapped[str | None] = mapped_column(String(64), index=True)
    leadout_offset: Mapped[int | None] = mapped_column(Integer)
    bp_disc_id: Mapped[str | None] = mapped_column(String(64), index=True)
    media_condition: Mapped[str | None] = mapped_column(String(100))
    sound_type: Mapped[str | None] = mapped_column(String(50))
    vinyl_color: Mapped[str | None] = mapped_column(String(100))
    vinyl_weight: Mapped[str | None] = mapped_column(String(100))
    rpm: Mapped[int | None] = mapped_column(Integer)
    spars: Mapped[str | None] = mapped_column(String(50))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MusicRelease] = relationship(back_populates="mediums")
    tracks: Mapped[list["MusicTrack"]] = relationship(
        back_populates="medium",
        cascade="all, delete-orphan",
    )


class MusicTrack(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_tracks"
    __table_args__ = (
        UniqueConstraint("medium_id", "position", name="unique_music_track"),
        Index("idx_music_tracks_medium_id", "medium_id"),
    )

    medium_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("music_mediums.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    offset_ms: Mapped[int | None] = mapped_column(Integer)
    bitrate_kbps: Mapped[int | None] = mapped_column(Integer)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    track_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    instrument: Mapped[str | None] = mapped_column(String(100))
    composition: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    medium: Mapped[MusicMedium] = relationship(back_populates="tracks")


class MusicReleaseContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_release_contributions"
    __table_args__ = (
        UniqueConstraint("release_id", "person_id", "role", name="unique_music_release_contribution"),
        Index("idx_music_release_contributions_release_id", "release_id"),
        Index("idx_music_release_contributions_role", "release_id", "role"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_id: Mapped[str | None] = mapped_column(String(64), index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MusicRelease] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class MusicReleaseIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_release_identifiers"
    __table_args__ = (
        UniqueConstraint("release_id", "identifier_type", "value", name="unique_music_release_identifier"),
        Index("idx_music_release_identifiers_release_id", "release_id"),
        Index("idx_music_release_identifiers_type_value", "identifier_type", "value"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False), index=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MusicRelease] = relationship(back_populates="identifiers")
