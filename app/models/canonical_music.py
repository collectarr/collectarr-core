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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import Base, ExternalProvider, TimestampMixin, UuidMixin
from app.models.canonical_support import EntityLink, Organization, Person


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
    original_release_date_parts: Mapped[str | None] = mapped_column(String(64))
    recording_date: Mapped[date | None] = mapped_column(Date)
    recording_date_parts: Mapped[str | None] = mapped_column(String(64))
    studio: Mapped[str | None] = mapped_column(String(255))
    is_live: Mapped[bool | None] = mapped_column(Boolean)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))

    releases: Mapped[list["MusicRelease"]] = relationship(
        back_populates="release_group",
        cascade="all, delete-orphan",
    )
    genre_entries: Mapped[list["MusicReleaseGroupGenre"]] = relationship(
        back_populates="release_group",
        cascade="all, delete-orphan",
        order_by="MusicReleaseGroupGenre.position",
    )
    artist_credits: Mapped[list["MusicArtistCredit"]] = relationship(
        primaryjoin=lambda: MusicReleaseGroup.id == foreign(MusicArtistCredit.release_group_id),
        cascade="all, delete-orphan",
        overlaps="release,group",
        order_by="MusicArtistCredit.sequence",
    )
    entity_links: Mapped[list["EntityLink"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityLink.entity_id) == MusicReleaseGroup.id,
            EntityLink.entity_type == "music_release_group",
        ),
        order_by="EntityLink.position",
        viewonly=True,
    )

    @property
    def genres(self) -> list[str]:
        return [entry.value for entry in self.genre_entries]


class MusicReleaseGroupGenre(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_release_group_genres"
    __table_args__ = (
        UniqueConstraint("release_group_id", "normalized_value", name="uq_music_release_group_genre"),
        Index("ix_music_release_group_genres_group_position", "release_group_id", "position"),
    )

    release_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_release_groups.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    release_group: Mapped[MusicReleaseGroup] = relationship(back_populates="genre_entries")


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
    release_date_parts: Mapped[str | None] = mapped_column(String(64))
    publisher: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(2))
    language: Mapped[str | None] = mapped_column(String(2))
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    upc: Mapped[str | None] = mapped_column(String(100), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    packaging: Mapped[str | None] = mapped_column(String(100))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))

    release_group: Mapped[MusicReleaseGroup] = relationship(back_populates="releases")
    mediums: Mapped[list["MusicMedium"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["MusicReleaseContribution"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    artist_credits: Mapped[list["MusicArtistCredit"]] = relationship(
        primaryjoin=lambda: MusicRelease.id == foreign(MusicArtistCredit.release_id),
        cascade="all, delete-orphan",
        overlaps="release_group,group",
        order_by="MusicArtistCredit.sequence",
    )
    labels: Mapped[list["MusicReleaseLabel"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
        order_by="MusicReleaseLabel.sequence",
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

    release: Mapped[MusicRelease] = relationship(back_populates="mediums")
    tracks: Mapped[list["MusicTrack"]] = relationship(
        back_populates="medium",
        cascade="all, delete-orphan",
    )
    missing_track_entries: Mapped[list["MusicMediumMissingTrackPosition"]] = relationship(
        back_populates="medium",
        cascade="all, delete-orphan",
        order_by="MusicMediumMissingTrackPosition.position_order",
    )


class MusicMediumMissingTrackPosition(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_medium_missing_track_positions"
    __table_args__ = (
        UniqueConstraint("medium_id", "position", name="uq_music_medium_missing_track_position"),
        Index("ix_music_medium_missing_track_positions_medium", "medium_id", "position_order"),
    )

    medium_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_mediums.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[str] = mapped_column(String(16), nullable=False)
    position_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    medium: Mapped[MusicMedium] = relationship(back_populates="missing_track_entries")


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
    artist: Mapped[str | None] = mapped_column(String(500))
    is_header: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    indent_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_header_id: Mapped[str | None] = mapped_column(String(36))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    offset_ms: Mapped[int | None] = mapped_column(Integer)
    bitrate_kbps: Mapped[int | None] = mapped_column(Integer)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    track_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    instrument: Mapped[str | None] = mapped_column(String(100))
    composition: Mapped[str | None] = mapped_column(String(255))

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

    release: Mapped[MusicRelease] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class MusicArtistCredit(UuidMixin, TimestampMixin, Base):
    """Lossless credited-artist display for a group or concrete release."""

    __tablename__ = "music_artist_credits"
    __table_args__ = (
        Index("idx_music_artist_credits_group", "release_group_id", "sequence"),
        Index("idx_music_artist_credits_release", "release_id", "sequence"),
    )

    release_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_release_groups.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), index=True
    )
    artist_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), index=True
    )
    credited_name: Mapped[str] = mapped_column(String(500), nullable=False)
    join_phrase: Mapped[str | None] = mapped_column(String(100))
    sequence: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(64))

    person: Mapped["Person | None"] = relationship()


class MusicReleaseLabel(UuidMixin, TimestampMixin, Base):
    """A release label and its catalog number as an inseparable pair."""

    __tablename__ = "music_release_labels"
    __table_args__ = (
        Index("idx_music_release_labels_release", "release_id", "sequence"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), index=True
    )
    label_name: Mapped[str] = mapped_column(String(255), nullable=False)
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    sequence: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(64))

    release: Mapped[MusicRelease] = relationship(back_populates="labels")
    label: Mapped["Organization | None"] = relationship()


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

    release: Mapped[MusicRelease] = relationship(back_populates="identifiers")
