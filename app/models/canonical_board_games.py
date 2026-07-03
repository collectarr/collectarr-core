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
    identifier_entries: Mapped[list["BoardGameIdentifier"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    contribution_entries: Mapped[list["BoardGameContribution"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    mechanic_entries: Mapped[list["BoardGameMechanic"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    category_entries: Mapped[list["BoardGameCategory"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    family_entries: Mapped[list["BoardGameFamily"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    expansion_entries: Mapped[list["BoardGameExpansion"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    ranking_snapshots: Mapped[list["BoardGameRankingSnapshot"]] = relationship(
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
        return _clean_text_list(values)

    @property
    def platforms(self) -> list[str]:
        return self._metadata_list("platforms")

    @property
    def identifiers(self) -> list[str]:
        return _clean_text_list([row.value for row in self.identifier_entries]) or self._metadata_list("identifiers")

    @property
    def contributors(self) -> list[str]:
        return _clean_text_list([row.person.name for row in self.contribution_entries if row.person is not None]) or self._metadata_list("contributors")

    @property
    def mechanics(self) -> list[str]:
        return _clean_text_list([row.value for row in self.mechanic_entries]) or self._metadata_list("mechanics")

    @property
    def categories(self) -> list[str]:
        return _clean_text_list([row.value for row in self.category_entries]) or self._metadata_list("categories")

    @property
    def families(self) -> list[str]:
        return _clean_text_list([row.value for row in self.family_entries]) or self._metadata_list("families")

    @property
    def expansions(self) -> list[str]:
        return _clean_text_list([row.value for row in self.expansion_entries]) or self._metadata_list("expansions")

    @property
    def rankings(self) -> list[str]:
        return _clean_text_list([row.ranking_name for row in self.ranking_snapshots]) or self._metadata_list("rankings")


class BoardGameIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "work_id",
            "identifier_type",
            "normalized_value",
            name="uq_boardgame_identifiers_work_type_normalized",
        ),
        Index("ix_boardgame_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BoardGameWork] = relationship(back_populates="identifier_entries")


class BoardGameContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_contributions"
    __table_args__ = (
        UniqueConstraint("work_id", "person_id", "role", name="uq_boardgame_contributions_work_person_role"),
        Index("ix_boardgame_contributions_work_role_sequence", "work_id", "role", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BoardGameWork] = relationship(back_populates="contribution_entries")
    person: Mapped["Person"] = relationship()


class BoardGameMechanic(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_mechanics"
    __table_args__ = (
        UniqueConstraint("work_id", "normalized_value", name="uq_boardgame_mechanics_work_normalized"),
        Index("ix_boardgame_mechanics_work_sequence", "work_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BoardGameWork] = relationship(back_populates="mechanic_entries")


class BoardGameCategory(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_categories"
    __table_args__ = (
        UniqueConstraint("work_id", "normalized_value", name="uq_boardgame_categories_work_normalized"),
        Index("ix_boardgame_categories_work_sequence", "work_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BoardGameWork] = relationship(back_populates="category_entries")


class BoardGameFamily(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_families"
    __table_args__ = (
        UniqueConstraint("work_id", "normalized_value", name="uq_boardgame_families_work_normalized"),
        Index("ix_boardgame_families_work_sequence", "work_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BoardGameWork] = relationship(back_populates="family_entries")


class BoardGameExpansion(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_expansions"
    __table_args__ = (
        UniqueConstraint("work_id", "normalized_value", name="uq_boardgame_expansions_work_normalized"),
        Index("ix_boardgame_expansions_work_sequence", "work_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BoardGameWork] = relationship(back_populates="expansion_entries")


class BoardGameRankingSnapshot(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_rankings_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "work_id",
            "ranking_name",
            "snapshot_date",
            name="uq_boardgame_rankings_snapshot_work_ranking_snapshot",
        ),
        Index("ix_boardgame_rankings_snapshot_work_date", "work_id", "snapshot_date"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ranking_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rank_position: Mapped[int | None] = mapped_column(Integer)
    users_rated: Mapped[int | None] = mapped_column(Integer)
    bayes_average: Mapped[float | None] = mapped_column(Float)
    snapshot_date: Mapped[date | None] = mapped_column(Date, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BoardGameWork] = relationship(back_populates="ranking_snapshots")


class BoardGamePlayerCountVote(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_player_count_votes"
    __table_args__ = (
        UniqueConstraint(
            "edition_id",
            "players_min",
            "players_max",
            name="uq_boardgame_player_count_votes_edition_range",
        ),
        Index("ix_boardgame_player_count_votes_edition", "edition_id"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    players_min: Mapped[int | None] = mapped_column(Integer)
    players_max: Mapped[int | None] = mapped_column(Integer)
    vote_count: Mapped[int | None] = mapped_column(Integer)
    recommended_count: Mapped[int | None] = mapped_column(Integer)
    not_recommended_count: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    edition: Mapped["BoardGameEdition"] = relationship(back_populates="player_count_votes")


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
    player_count_votes: Mapped[list[BoardGamePlayerCountVote]] = relationship(
        back_populates="edition",
        cascade="all, delete-orphan",
    )

    def _metadata_list(self, key: str) -> list[str]:
        values = self.metadata_json.get(key) if isinstance(self.metadata_json, dict) else None
        return _clean_text_list(values)

    @property
    def identifiers(self) -> list[str]:
        return self._metadata_list("identifiers")
