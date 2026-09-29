"""Flattened Anime Catalog Items with contained media and episode rows."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin


class AnimeItem(UuidMixin, TimestampMixin, Base):
    """One concrete Anime season, part, or box-set release."""

    __tablename__ = "anime_items"
    __table_args__ = (
        Index("ix_anime_items_title", "title"),
        Index(
            "ix_anime_items_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_anime_items_sort_key", "sort_key"),
        Index(
            "ix_anime_items_sort_key_trgm",
            "sort_key",
            postgresql_using="gin",
            postgresql_ops={"sort_key": "gin_trgm_ops"},
        ),
        Index("ix_anime_items_barcode", "barcode"),
        Index("ix_anime_items_catalog_number", "catalog_number"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_key: Mapped[str | None] = mapped_column(String(255))
    barcode: Mapped[str | None] = mapped_column(String(100))
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}

    media: Mapped[list["AnimeItemMedia"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="AnimeItemMedia.position"
    )
    episodes: Mapped[list["AnimeItemEpisode"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="AnimeItemEpisode.position"
    )
    identifiers: Mapped[list["AnimeItemIdentifier"]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
        order_by="AnimeItemIdentifier.identifier_type",
    )


class AnimeItemMedia(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_item_media"
    __table_args__ = (
        UniqueConstraint("anime_item_id", "position", name="uq_anime_item_media_position"),
        Index("ix_anime_item_media_number", "anime_item_id", "media_number"),
    )

    anime_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_items.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    media_number: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    item: Mapped[AnimeItem] = relationship(back_populates="media")


class AnimeItemEpisode(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_item_episodes"
    __table_args__ = (
        UniqueConstraint("anime_item_id", "position", name="uq_anime_item_episode_position"),
        Index("ix_anime_item_episodes_number", "anime_item_id", "episode_number"),
    )

    anime_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_items.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    episode_number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    item: Mapped[AnimeItem] = relationship(back_populates="episodes")


class AnimeItemIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_item_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "anime_item_id", "identifier_type", "normalized_value",
            name="uq_anime_item_identifier_normalized",
        ),
        Index("ix_anime_item_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    anime_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_items.id", ondelete="CASCADE"), nullable=False
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    item: Mapped[AnimeItem] = relationship(back_populates="identifiers")
