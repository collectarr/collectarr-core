from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
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


class TVRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_releases"
    __table_args__ = (
        Index("idx_tv_releases_sort_title", "sort_title"),
        Index("idx_tv_releases_sku", "sku"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    media_count: Mapped[int | None] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(64), nullable=False)
    region_code: Mapped[str | None] = mapped_column(String(2))
    release_date: Mapped[date | None] = mapped_column(Date)
    publisher: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    case_type: Mapped[str | None] = mapped_column(String(64))
    episode_count: Mapped[int | None] = mapped_column(Integer)
    season_count: Mapped[int | None] = mapped_column(Integer)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    language_audio: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    language_subtitles: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    content_rating: Mapped[str | None] = mapped_column(String(64))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    series: Mapped["TVSeries"] = relationship(back_populates="releases")
    media: Mapped[list["TVReleaseMedia"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    episodes: Mapped[list["TVEpisode"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["TVReleaseContribution"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["TVReleaseIdentifier"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    episode_mappings: Mapped[list["TVReleaseEpisodeMap"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )


class TVSeries(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_series"
    __table_args__ = (
        Index("idx_tv_series_sort_title", "sort_title"),
        Index("idx_tv_series_first_air_date", "first_air_date"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_title: Mapped[str | None] = mapped_column(String(255), index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    overview: Mapped[str | None] = mapped_column(Text)
    first_air_date: Mapped[date | None] = mapped_column(Date)
    last_air_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(64))
    type: Mapped[str | None] = mapped_column(String(64))
    network: Mapped[str | None] = mapped_column(String(255))
    original_language: Mapped[str | None] = mapped_column(String(16))
    country: Mapped[str | None] = mapped_column(String(16))
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    season_count: Mapped[int | None] = mapped_column(Integer)
    episode_count: Mapped[int | None] = mapped_column(Integer)
    poster_url: Mapped[str | None] = mapped_column(String(2048))
    backdrop_url: Mapped[str | None] = mapped_column(String(2048))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    seasons: Mapped[list["TVSeason"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )
    episodes: Mapped[list["TVEpisode"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )
    releases: Mapped[list["TVRelease"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )


class TVSeason(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_seasons"
    __table_args__ = (
        UniqueConstraint("series_id", "season_number", name="unique_tv_season"),
        Index("idx_tv_seasons_series_id", "series_id"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    overview: Mapped[str | None] = mapped_column(Text)
    air_date: Mapped[date | None] = mapped_column(Date)
    episode_count: Mapped[int | None] = mapped_column(Integer)
    poster_url: Mapped[str | None] = mapped_column(String(2048))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    series: Mapped["TVSeries"] = relationship(back_populates="seasons")
    episodes: Mapped[list["TVEpisode"]] = relationship(
        back_populates="season",
        cascade="all, delete-orphan",
    )


class TVReleaseMedia(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_release_media"
    __table_args__ = (
        UniqueConstraint("release_id", "media_number", name="unique_tv_release_media"),
        Index("idx_tv_release_media_release_id", "release_id"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_number: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    episode_count: Mapped[int | None] = mapped_column(Integer)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    region_code: Mapped[str | None] = mapped_column(String(2))
    encoding: Mapped[str | None] = mapped_column(String(64))
    aspect_ratio: Mapped[str | None] = mapped_column(String(16))
    color: Mapped[str | None] = mapped_column(String(64))
    audio_tracks: Mapped[str | None] = mapped_column(String(500))
    subtitles: Mapped[str | None] = mapped_column(String(500))
    layers: Mapped[str | None] = mapped_column(String(50))
    frame_rate: Mapped[str | None] = mapped_column(String(16))
    bit_depth: Mapped[str | None] = mapped_column(String(16))
    resolution: Mapped[str | None] = mapped_column(String(16))
    hdr_format: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[TVRelease] = relationship(back_populates="media")
    episodes: Mapped[list["TVEpisode"]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )
    episode_mappings: Mapped[list["TVReleaseEpisodeMap"]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )


class TVEpisode(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_episodes"
    __table_args__ = (
        UniqueConstraint("series_id", "season_id", "episode_number", name="unique_tv_episode"),
        Index("idx_tv_episodes_series_id", "series_id"),
        Index("idx_tv_episodes_season_id", "season_id"),
        Index("idx_tv_episodes_release_id", "release_id"),
        Index("idx_tv_episodes_media_id", "media_id"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_seasons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_releases.id", ondelete="SET NULL"), index=True
    )
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_release_media.id", ondelete="SET NULL"), index=True
    )
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    original_air_date: Mapped[date | None] = mapped_column(Date)
    still_url: Mapped[str | None] = mapped_column(String(2048))
    image_url: Mapped[str | None] = mapped_column(String(2048))
    large_image_url: Mapped[str | None] = mapped_column(String(2048))
    still_key: Mapped[str | None] = mapped_column(String(512))
    production_code: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    series: Mapped["TVSeries"] = relationship(back_populates="episodes")
    season: Mapped["TVSeason"] = relationship(back_populates="episodes")
    release: Mapped[TVRelease] = relationship(back_populates="episodes")
    media: Mapped[TVReleaseMedia] = relationship(back_populates="episodes")
    identifiers: Mapped[list["TVEpisodeIdentifier"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["TVEpisodeContribution"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
    )
    release_mappings: Mapped[list["TVReleaseEpisodeMap"]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
    )


class TVReleaseEpisodeMap(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_release_episode_map"
    __table_args__ = (
        UniqueConstraint("release_id", "media_id", "episode_id", name="unique_tv_release_episode_map"),
        Index("idx_tv_release_episode_map_release_id", "release_id"),
        Index("idx_tv_release_episode_map_media_id", "media_id"),
        Index("idx_tv_release_episode_map_episode_id", "episode_id"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_release_media.id", ondelete="CASCADE"), nullable=False, index=True
    )
    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    disc_number: Mapped[int | None] = mapped_column(Integer)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[TVRelease] = relationship(back_populates="episode_mappings")
    media: Mapped[TVReleaseMedia] = relationship(back_populates="episode_mappings")
    episode: Mapped[TVEpisode] = relationship(back_populates="release_mappings")


class TVEpisodeIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_episode_identifiers"
    __table_args__ = (
        UniqueConstraint("episode_id", "identifier_type", "value", name="unique_tv_episode_identifier"),
        Index("idx_tv_episode_identifiers_episode_id", "episode_id"),
        Index("idx_tv_episode_identifiers_type_value", "identifier_type", "value"),
    )

    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    episode: Mapped[TVEpisode] = relationship(back_populates="identifiers")


class TVEpisodeContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_episode_contributions"
    __table_args__ = (
        UniqueConstraint("episode_id", "person_id", "role", name="unique_tv_episode_contribution"),
        Index("idx_tv_episode_contributions_episode_id", "episode_id"),
        Index("idx_tv_episode_contributions_person_id", "person_id"),
        Index("idx_tv_episode_contributions_role", "episode_id", "role"),
    )

    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    character_name: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    episode: Mapped[TVEpisode] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class TVReleaseContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_release_contributions"
    __table_args__ = (
        UniqueConstraint("release_id", "person_id", "role", name="unique_tv_release_contribution"),
        Index("idx_tv_release_contributions_release_id", "release_id"),
        Index("idx_tv_release_contributions_person_id", "person_id"),
        Index("idx_tv_release_contributions_role", "release_id", "role"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    character_name: Mapped[str | None] = mapped_column(String(255))
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[TVRelease] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class TVReleaseIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_release_identifiers"
    __table_args__ = (
        UniqueConstraint("release_id", "identifier_type", "value", name="unique_tv_release_identifier"),
        Index("idx_tv_release_identifiers_release_id", "release_id"),
        Index("idx_tv_release_identifiers_type_value", "identifier_type", "value"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[TVRelease] = relationship(back_populates="identifiers")


# ========================
# Music v1 Schema
# ========================


class MusicRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_releases"
    __table_args__ = (
        Index("idx_music_releases_barcode", "barcode"),
        Index("idx_music_releases_created_at", "created_at"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    release_type: Mapped[str | None] = mapped_column(String(64))
    release_status: Mapped[str | None] = mapped_column(String(50))
    release_date: Mapped[date | None] = mapped_column(Date)
    recording_date: Mapped[date | None] = mapped_column(Date)
    media_count: Mapped[int | None] = mapped_column(Integer)
    expected_media_count: Mapped[int | None] = mapped_column(Integer)
    missing_media_count: Mapped[int | None] = mapped_column(Integer)
    missing_disc_numbers: Mapped[list[int] | None] = mapped_column(JSONB)
    track_count: Mapped[int | None] = mapped_column(Integer)
    upc: Mapped[str | None] = mapped_column(String(100), index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    publisher: Mapped[str | None] = mapped_column(String(255))
    studio: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(2))
    language: Mapped[str | None] = mapped_column(String(2))
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    audience_rating: Mapped[float | None] = mapped_column(Float)
    rating_count: Mapped[int | None] = mapped_column(Integer)
    extras: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    media: Mapped[list["MusicMedia"]] = relationship(
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


class MusicMedia(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_media"
    __table_args__ = (
        UniqueConstraint("release_id", "media_number", name="unique_music_media"),
        Index("idx_music_media_release_id", "release_id"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_number: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))
    track_count: Mapped[int | None] = mapped_column(Integer)
    expected_track_count: Mapped[int | None] = mapped_column(Integer)
    missing_track_count: Mapped[int | None] = mapped_column(Integer)
    missing_track_positions: Mapped[list[str] | None] = mapped_column(JSONB)
    toc: Mapped[str | None] = mapped_column(Text)
    cddb_id: Mapped[str | None] = mapped_column(String(64), index=True)
    leadout_offset: Mapped[int | None] = mapped_column(Integer)
    bp_disc_id: Mapped[str | None] = mapped_column(String(64), index=True)
    packaging: Mapped[str | None] = mapped_column(String(100))
    media_condition: Mapped[str | None] = mapped_column(String(100))
    sound_type: Mapped[str | None] = mapped_column(String(50))
    vinyl_color: Mapped[str | None] = mapped_column(String(100))
    vinyl_weight: Mapped[str | None] = mapped_column(String(100))
    rpm: Mapped[int | None] = mapped_column(Integer)
    spars: Mapped[str | None] = mapped_column(String(50))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MusicRelease] = relationship(back_populates="media")
    tracks: Mapped[list["MusicTrack"]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )


class MusicTrack(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_tracks"
    __table_args__ = (
        UniqueConstraint("media_id", "position", name="unique_music_track"),
        Index("idx_music_tracks_release_id", "release_id"),
    )

    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_media.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), nullable=False, index=True
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

    media: Mapped[MusicMedia] = relationship(back_populates="tracks")
    release: Mapped[MusicRelease] = relationship()


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
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MusicRelease] = relationship(back_populates="identifiers")


# ========================
# Movie v1 Schema
# ========================


class MovieWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_works"
    __table_args__ = (
        Index("idx_movie_works_created_at", "created_at"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(2))
    original_title: Mapped[str | None] = mapped_column(String(255))
    original_release_date: Mapped[date | None] = mapped_column(Date)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(64))
    budget_usd: Mapped[int | None] = mapped_column(Integer)
    revenue_usd: Mapped[int | None] = mapped_column(Integer)
    age_rating: Mapped[str | None] = mapped_column(String(20))
    audience_rating: Mapped[str | None] = mapped_column(String(50))
    rating_count: Mapped[int | None] = mapped_column(Integer)
    poster_image_url: Mapped[str | None] = mapped_column(String(2048))
    poster_image_key: Mapped[str | None] = mapped_column(String(512))
    backdrop_image_url: Mapped[str | None] = mapped_column(String(2048))
    backdrop_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    releases: Mapped[list["MovieRelease"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["MovieWorkContribution"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["MovieWorkIdentifier"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )


class MovieRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_releases"
    __table_args__ = (
        UniqueConstraint("work_id", "region_code", "format", name="unique_movie_release"),
        Index("idx_movie_releases_work_id", "work_id"),
        Index("idx_movie_releases_barcode", "barcode"),
        Index("idx_movie_releases_created_at", "created_at"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movie_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format: Mapped[str] = mapped_column(String(64), nullable=False)
    region_code: Mapped[str | None] = mapped_column(String(2))
    release_date: Mapped[date | None] = mapped_column(Date)
    release_type: Mapped[str | None] = mapped_column(String(64))
    certification: Mapped[str | None] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(64))
    publisher: Mapped[str | None] = mapped_column(String(255))
    distributor: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    media_count: Mapped[int | None] = mapped_column(Integer)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    language_audio: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    language_subtitles: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    work: Mapped[MovieWork] = relationship(back_populates="releases")
    media: Mapped[list["MovieReleaseMedia"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )


class MovieReleaseMedia(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_release_media"
    __table_args__ = (
        UniqueConstraint("release_id", "media_number", name="unique_movie_release_media"),
        Index("idx_movie_release_media_release_id", "release_id"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movie_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_number: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))
    aspect_ratio: Mapped[str | None] = mapped_column(String(16))
    screen_ratio: Mapped[str | None] = mapped_column(String(50))
    color: Mapped[str | None] = mapped_column(String(64))
    num_discs: Mapped[int | None] = mapped_column(Integer)
    nr_layers: Mapped[int | None] = mapped_column(Integer)
    layers: Mapped[str | None] = mapped_column(String(50))
    audio_tracks: Mapped[str | None] = mapped_column(String(500))
    subtitles: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MovieRelease] = relationship(back_populates="media")


class MovieWorkContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_work_contributions"
    __table_args__ = (
        UniqueConstraint("work_id", "person_id", "role", name="unique_movie_work_contribution"),
        Index("idx_movie_work_contributions_work_id", "work_id"),
        Index("idx_movie_work_contributions_role", "work_id", "role"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movie_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    character_name: Mapped[str | None] = mapped_column(String(255))
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    work: Mapped[MovieWork] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class MovieWorkIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_work_identifiers"
    __table_args__ = (
        UniqueConstraint("work_id", "identifier_type", "value", name="unique_movie_work_identifier"),
        Index("idx_movie_work_identifiers_work_id", "work_id"),
        Index("idx_movie_work_identifiers_type_value", "identifier_type", "value"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movie_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    work: Mapped[MovieWork] = relationship(back_populates="identifiers")
