"""Flattened TV Catalog Items with contained season, media, and episode rows."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin


class TvItem(UuidMixin, TimestampMixin, Base):
    """One concrete TV season release or box set."""

    __tablename__ = "tv_items"
    __table_args__ = (
        Index("ix_tv_items_title", "title"),
        Index(
            "ix_tv_items_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_tv_items_sort_key", "sort_key"),
        Index(
            "ix_tv_items_sort_key_trgm",
            "sort_key",
            postgresql_using="gin",
            postgresql_ops={"sort_key": "gin_trgm_ops"},
        ),
        Index("ix_tv_items_barcode", "barcode"),
        Index("ix_tv_items_catalog_number", "catalog_number"),
        Index(
            "ix_tv_items_details_gin",
            "details",
            postgresql_using="gin",
            postgresql_ops={"details": "jsonb_path_ops"},
        ),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_key: Mapped[str | None] = mapped_column(String(255))
    barcode: Mapped[str | None] = mapped_column(String(100))
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}

    seasons: Mapped[list["TvItemSeason"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="TvItemSeason.season_number"
    )
    media: Mapped[list["TvItemMedia"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="TvItemMedia.position"
    )
    episodes: Mapped[list["TvItemEpisode"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="TvItemEpisode.position"
    )
    identifiers: Mapped[list["TvItemIdentifier"]] = relationship(
        back_populates="item", cascade="all, delete-orphan",
        order_by="TvItemIdentifier.identifier_type",
    )


class TvItemSeason(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_item_seasons"
    __table_args__ = (
        UniqueConstraint("tv_item_id", "season_number", name="uq_tv_item_season_number"),
    )

    tv_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_items.id", ondelete="CASCADE"), nullable=False
    )
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    item: Mapped[TvItem] = relationship(back_populates="seasons")


class TvItemMedia(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_item_media"
    __table_args__ = (
        UniqueConstraint("tv_item_id", "position", name="uq_tv_item_media_position"),
        Index("ix_tv_item_media_number", "tv_item_id", "media_number"),
    )

    tv_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_items.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    media_number: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    item: Mapped[TvItem] = relationship(back_populates="media")


class TvItemEpisode(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_item_episodes"
    __table_args__ = (
        UniqueConstraint("tv_item_id", "position", name="uq_tv_item_episode_position"),
        Index("ix_tv_item_episodes_coordinates", "tv_item_id", "season_number", "episode_number"),
    )

    tv_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_items.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    season_number: Mapped[int | None] = mapped_column(Integer)
    episode_number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    item: Mapped[TvItem] = relationship(back_populates="episodes")


class TvItemIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_item_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "tv_item_id", "identifier_type", "normalized_value",
            name="uq_tv_item_identifier_normalized",
        ),
        Index("ix_tv_item_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    tv_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_items.id", ondelete="CASCADE"), nullable=False
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    item: Mapped[TvItem] = relationship(back_populates="identifiers")
