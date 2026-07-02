from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
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
    StoryArc,
    StoryArcItem,
    Tag,
)


class BoardGameWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_works"

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

    editions: Mapped[list["BoardGameEdition"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    person_links: Mapped[list["EntityPerson"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityPerson.entity_id) == BoardGameWork.id,
            EntityPerson.entity_type == "boardgame_work",
        ),
        viewonly=True,
    )
    organization_links: Mapped[list["EntityOrganization"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityOrganization.entity_id) == BoardGameWork.id,
            EntityOrganization.entity_type == "boardgame_work",
        ),
        viewonly=True,
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == BoardGameWork.id,
            ExternalProviderId.entity_type == "boardgame_work",
        ),
        viewonly=True,
    )

    def _metadata_list(self, key: str) -> list[str]:
        values = self.metadata_json.get(key) if isinstance(self.metadata_json, dict) else None
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

    @property
    def platforms(self) -> list[str]:
        return self._metadata_list("platforms")

    @property
    def identifiers(self) -> list[str]:
        return self._metadata_list("identifiers")

    @property
    def contributors(self) -> list[str]:
        return self._metadata_list("contributors")

    @property
    def mechanics(self) -> list[str]:
        return self._metadata_list("mechanics")

    @property
    def categories(self) -> list[str]:
        return self._metadata_list("categories")

    @property
    def families(self) -> list[str]:
        return self._metadata_list("families")

    @property
    def expansions(self) -> list[str]:
        return self._metadata_list("expansions")

    @property
    def rankings(self) -> list[str]:
        return self._metadata_list("rankings")


class BoardGameEdition(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_editions"
    __table_args__ = (
        Index("ix_boardgame_editions_work_release", "work_id", "release_date"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edition_title: Mapped[str | None] = mapped_column(String(255))
    format: Mapped[str | None] = mapped_column(String(64))
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    country: Mapped[str | None] = mapped_column(String(32), index=True)
    age_rating: Mapped[str | None] = mapped_column(String(64), index=True)
    audience_rating: Mapped[str | None] = mapped_column(String(64))
    min_players: Mapped[int | None] = mapped_column(Integer)
    max_players: Mapped[int | None] = mapped_column(Integer)
    playing_time_minutes: Mapped[int | None] = mapped_column(Integer)
    min_age: Mapped[int | None] = mapped_column(Integer)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BoardGameWork] = relationship(back_populates="editions")

    def _metadata_list(self, key: str) -> list[str]:
        values = self.metadata_json.get(key) if isinstance(self.metadata_json, dict) else None
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

    @property
    def identifiers(self) -> list[str]:
        return self._metadata_list("identifiers")
