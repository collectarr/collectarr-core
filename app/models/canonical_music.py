from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    ForeignKey,
    UniqueConstraint,
    and_,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin
from app.models.canonical_support import EntityLink


class MusicAlbum(UuidMixin, TimestampMixin, Base):
    """One catalog edition of an album, independent of any provider."""

    __tablename__ = "music_albums"
    __table_args__ = (
        Index("idx_music_albums_title", "title"),
        Index("idx_music_albums_sort_title", "sort_title"),
        Index("idx_music_albums_barcode", "barcode"),
        Index("idx_music_albums_catalog_number", "catalog_number"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    artists: Mapped[list[dict[str, str | None]]] = mapped_column(JSON, nullable=False, default=list)
    release_date: Mapped[date | None] = mapped_column(Date)
    release_date_parts: Mapped[str | None] = mapped_column(String(64))
    original_release_date: Mapped[date | None] = mapped_column(Date)
    original_release_date_parts: Mapped[str | None] = mapped_column(String(64))
    recording_date: Mapped[date | None] = mapped_column(Date)
    recording_date_parts: Mapped[str | None] = mapped_column(String(64))
    labels: Mapped[list[dict[str, str | None]]] = mapped_column(JSON, nullable=False, default=list)
    format: Mapped[str | None] = mapped_column(String(100))
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100), index=True)
    genres: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    packaging: Mapped[str | None] = mapped_column(String(100))
    studio: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    country: Mapped[str | None] = mapped_column(String(64))
    is_live: Mapped[bool | None] = mapped_column(Boolean)
    sound_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    vinyl_color: Mapped[str | None] = mapped_column(String(100))
    vinyl_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    rpm: Mapped[int | None] = mapped_column(Integer)
    extras: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    spars_code: Mapped[str | None] = mapped_column(String(50))
    box_set: Mapped[str | None] = mapped_column(String(255))
    matrix_number_side_a: Mapped[str | None] = mapped_column(String(255))
    matrix_number_side_b: Mapped[str | None] = mapped_column(String(255))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    back_cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    back_cover_image_key: Mapped[str | None] = mapped_column(String(512))

    credits: Mapped[list[MusicAlbumCredit]] = relationship(
        back_populates="album",
        cascade="all, delete-orphan",
        order_by="MusicAlbumCredit.sequence",
    )
    disc_titles: Mapped[list[MusicAlbumDiscTitle]] = relationship(
        back_populates="album",
        cascade="all, delete-orphan",
        order_by="MusicAlbumDiscTitle.disc_number",
    )
    tracks: Mapped[list[MusicAlbumTrack]] = relationship(
        back_populates="album",
        cascade="all, delete-orphan",
        order_by="(MusicAlbumTrack.disc_number, MusicAlbumTrack.position)",
    )
    links: Mapped[list[EntityLink]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityLink.entity_id) == MusicAlbum.id,
            EntityLink.entity_type == "music_album",
            EntityLink.link_type == "external",
        ),
        order_by="EntityLink.position",
        viewonly=True,
    )


class MusicAlbumDiscTitle(Base):
    """An optional title contained by an album disc number; it has no public ID."""

    __tablename__ = "music_album_disc_titles"
    __table_args__ = (UniqueConstraint("album_id", "disc_number", name="uq_music_album_disc_title"),)

    album_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_albums.id", ondelete="CASCADE"), primary_key=True
    )
    disc_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    album: Mapped[MusicAlbum] = relationship(back_populates="disc_titles")


class MusicAlbumTrack(Base):
    """A track contained by an album, ordered within a one-based disc number."""

    __tablename__ = "music_album_tracks"
    __table_args__ = (
        UniqueConstraint("album_id", "disc_number", "position", name="uq_music_album_track_position"),
        Index("idx_music_album_tracks_album_disc", "album_id", "disc_number", "position"),
    )

    album_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_albums.id", ondelete="CASCADE"), primary_key=True
    )
    disc_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    artist: Mapped[str | None] = mapped_column(String(500))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    album: Mapped[MusicAlbum] = relationship(back_populates="tracks")


class MusicAlbumCredit(Base):
    """A role credit contained by an album, ordered within its role."""

    __tablename__ = "music_album_credits"
    __table_args__ = (
        UniqueConstraint("album_id", "role", "sequence", name="uq_music_album_credit_order"),
        Index("idx_music_album_credits_album_role", "album_id", "role", "sequence"),
    )

    album_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_albums.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(64), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    credited_name: Mapped[str] = mapped_column(String(500), nullable=False)
    join_phrase: Mapped[str | None] = mapped_column(String(100))
    instrument: Mapped[str | None] = mapped_column(String(100))

    album: Mapped[MusicAlbum] = relationship(back_populates="credits")
