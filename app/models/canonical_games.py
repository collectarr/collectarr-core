from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    String,
    Text,
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
    SeriesRelation,
    StoryArc,
    StoryArcItem,
    Tag,
)


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
