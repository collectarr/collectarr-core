from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
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


def _clean_text_list(values: list[Any] | None) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            continue
        marker = text.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(text)
    return result


class GameWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_works"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    original_language: Mapped[str | None] = mapped_column(String(16))
    age_rating: Mapped[str | None] = mapped_column(String(64))
    audience_rating: Mapped[str | None] = mapped_column(String(64))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    releases: Mapped[list["GameRelease"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    platform_entries: Mapped[list["GamePlatform"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    identifier_entries: Mapped[list["GameIdentifier"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    company_role_entries: Mapped[list["GameCompanyRole"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    age_rating_entries: Mapped[list["GameAgeRating"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    series_memberships: Mapped[list["GameSeriesMembership"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    organization_links: Mapped[list["EntityOrganization"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityOrganization.entity_id) == GameWork.id,
            EntityOrganization.entity_type == "game_work",
        ),
        viewonly=True,
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == GameWork.id,
            ExternalProviderId.entity_type == "game_work",
        ),
        viewonly=True,
    )

    def _metadata_list(self, key: str) -> list[str]:
        values = self.metadata_json.get(key) if isinstance(self.metadata_json, dict) else None
        return _clean_text_list(values)

    @property
    def platforms(self) -> list[str]:
        return _clean_text_list([row.platform_name for row in self.platform_entries]) or self._metadata_list("platforms")

    @property
    def identifiers(self) -> list[str]:
        return _clean_text_list([row.value for row in self.identifier_entries]) or self._metadata_list("identifiers")

    @property
    def company_roles(self) -> list[str]:
        return _clean_text_list([row.role for row in self.company_role_entries]) or self._metadata_list("company_roles")

    @property
    def age_ratings(self) -> list[str]:
        return _clean_text_list([row.rating for row in self.age_rating_entries]) or self._metadata_list("age_ratings")


class GamePlatform(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_platforms"
    __table_args__ = (
        UniqueConstraint("work_id", "normalized_name", name="uq_game_platforms_work_normalized_name"),
        Index("ix_game_platforms_work_position", "work_id", "is_primary", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[GameWork] = relationship(back_populates="platform_entries")


class GameReleasePlatform(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_release_platforms"
    __table_args__ = (
        UniqueConstraint("release_id", "platform_id", name="uq_game_release_platforms_release_platform"),
        Index("ix_game_release_platforms_release_primary", "release_id", "is_primary", "sequence"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_platforms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int | None] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    release: Mapped["GameRelease"] = relationship(back_populates="platform_links")
    platform: Mapped[GamePlatform] = relationship()


class GameIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_identifiers"
    __table_args__ = (
        UniqueConstraint("work_id", "identifier_type", "normalized_value", name="uq_game_identifiers_work_type_normalized"),
        Index("ix_game_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[GameWork] = relationship(back_populates="identifier_entries")


class GameCompanyRole(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_company_roles"
    __table_args__ = (
        UniqueConstraint("work_id", "organization_id", "role", name="uq_game_company_roles_work_org_role"),
        Index("ix_game_company_roles_work_role_sequence", "work_id", "role", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[GameWork] = relationship(back_populates="company_role_entries")
    organization: Mapped["Organization"] = relationship()


class GameAgeRating(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_age_ratings"
    __table_args__ = (
        UniqueConstraint("work_id", "rating_system", "rating", "region_code", name="uq_game_age_ratings_work_rating"),
        Index("ix_game_age_ratings_work_system", "work_id", "rating_system"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating_system: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rating: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    region_code: Mapped[str | None] = mapped_column(String(32), index=True)
    descriptor: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[GameWork] = relationship(back_populates="age_rating_entries")


class GameSeriesMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_series_memberships"
    __table_args__ = (
        UniqueConstraint("work_id", "normalized_series_name", name="uq_game_series_memberships_work_series"),
        Index("ix_game_series_memberships_work_sequence", "work_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_series_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sequence: Mapped[float | None] = mapped_column(Float)
    display_number: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[GameWork] = relationship(back_populates="series_memberships")


class GameRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_releases"
    __table_args__ = (
        Index("ix_game_releases_work_platform", "work_id", "platform"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_title: Mapped[str | None] = mapped_column(String(255))
    platform: Mapped[str | None] = mapped_column(String(128), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    region_code: Mapped[str | None] = mapped_column(String(32), index=True)
    format: Mapped[str | None] = mapped_column(String(64), index=True)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[GameWork] = relationship(back_populates="releases")
    platform_links: Mapped[list[GameReleasePlatform]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )

    def _metadata_list(self, key: str) -> list[str]:
        values = self.metadata_json.get(key) if isinstance(self.metadata_json, dict) else None
        return _clean_text_list(values)

    @property
    def identifiers(self) -> list[str]:
        return self._metadata_list("identifiers")
