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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UuidMixin,
)
from app.models.canonical_support import (  # noqa: F401
    AdminAuditLog,
    Character,
    CharacterAppearance,
    ComicSeriesRelation,
    EntityAlias,
    EntityLink,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ImageAsset,
    ImageCacheEntry,
    MangaSeriesRelation,
    Organization,
    Person,
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
    release_date_parts: Mapped[str | None] = mapped_column(String(64))
    original_language: Mapped[str | None] = mapped_column(String(16))
    age_rating: Mapped[str | None] = mapped_column(String(64))
    audience_rating: Mapped[str | None] = mapped_column(String(64))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))

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
    genre_entries: Mapped[list["BoardGameGenre"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
        order_by="BoardGameGenre.sequence",
    )
    platform_entries: Mapped[list["BoardGamePlatform"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
        order_by="BoardGamePlatform.sequence",
    )
    entity_links: Mapped[list["EntityLink"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityLink.entity_id) == BoardGameWork.id,
            EntityLink.entity_type == "boardgame_work",
        ),
        order_by="EntityLink.position",
        viewonly=True,
    )
    alias_entries: Mapped[list["EntityAlias"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityAlias.entity_id) == BoardGameWork.id,
            EntityAlias.entity_type == "boardgame_work",
        ),
        order_by="EntityAlias.position",
        viewonly=True,
    )

    @property
    def platforms(self) -> list[str]:
        return _clean_text_list([row.value for row in self.platform_entries])

    @property
    def identifiers(self) -> list[str]:
        return _clean_text_list([row.value for row in self.identifier_entries])

    @property
    def contributors(self) -> list[str]:
        return _clean_text_list([row.person.name for row in self.contribution_entries if row.person is not None])

    @property
    def mechanics(self) -> list[str]:
        return _clean_text_list([row.value for row in self.mechanic_entries])

    @property
    def categories(self) -> list[str]:
        return _clean_text_list([row.value for row in self.category_entries])

    @property
    def families(self) -> list[str]:
        return _clean_text_list([row.value for row in self.family_entries])

    @property
    def expansions(self) -> list[str]:
        return _clean_text_list([row.value for row in self.expansion_entries])

    @property
    def rankings(self) -> list[str]:
        return _clean_text_list([row.ranking_name for row in self.ranking_snapshots])

    @property
    def genres(self) -> list[str]:
        return _clean_text_list([row.value for row in self.genre_entries])


class BoardGameGenre(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_genres"
    __table_args__ = (
        UniqueConstraint("work_id", "normalized_value", name="uq_boardgame_genres_work_normalized"),
        Index("ix_boardgame_genres_work_sequence", "work_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    work: Mapped[BoardGameWork] = relationship(back_populates="genre_entries")


class BoardGamePlatform(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_platforms"
    __table_args__ = (
        UniqueConstraint("work_id", "normalized_value", name="uq_boardgame_platforms_work_normalized"),
        Index("ix_boardgame_platforms_work_sequence", "work_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    work: Mapped[BoardGameWork] = relationship(back_populates="platform_entries")


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
    snapshot_date_parts: Mapped[str | None] = mapped_column(String(64))

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
    release_date_parts: Mapped[str | None] = mapped_column(String(64))
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

    work: Mapped[BoardGameWork] = relationship(back_populates="editions")
    player_count_votes: Mapped[list[BoardGamePlayerCountVote]] = relationship(
        back_populates="edition",
        cascade="all, delete-orphan",
    )
    identifier_entries: Mapped[list["BoardGameEditionIdentifier"]] = relationship(
        back_populates="edition",
        cascade="all, delete-orphan",
    )

    @property
    def identifiers(self) -> list[str]:
        return _clean_text_list([row.value for row in self.identifier_entries])


class BoardGameEditionIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_edition_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "edition_id",
            "identifier_type",
            "normalized_value",
            name="uq_boardgame_edition_identifiers_edition_type_normalized",
        ),
        Index("ix_boardgame_edition_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    edition: Mapped[BoardGameEdition] = relationship(back_populates="identifier_entries")
