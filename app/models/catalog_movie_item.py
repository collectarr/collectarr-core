"""Flattened Movie Catalog Items and their contained media records."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin


class MovieItem(UuidMixin, TimestampMixin, Base):
    """One concrete Movie edition, without an editable work/release parent."""

    __tablename__ = "movie_items"
    __table_args__ = (
        Index("ix_movie_items_title", "title"),
        Index(
            "ix_movie_items_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_movie_items_sort_key", "sort_key"),
        Index(
            "ix_movie_items_sort_key_trgm",
            "sort_key",
            postgresql_using="gin",
            postgresql_ops={"sort_key": "gin_trgm_ops"},
        ),
        Index("ix_movie_items_barcode", "barcode"),
        Index("ix_movie_items_catalog_number", "catalog_number"),
        Index(
            "ix_movie_items_details_gin",
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

    media: Mapped[list["MovieItemMedia"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="MovieItemMedia.media_number",
    )


class MovieItemMedia(UuidMixin, TimestampMixin, Base):
    """A contained disc or other medium for one concrete Movie edition."""

    __tablename__ = "movie_item_media"
    __table_args__ = (
        UniqueConstraint(
            "movie_item_id",
            "media_number",
            name="uq_movie_item_media_number",
        ),
        Index("ix_movie_item_media_item", "movie_item_id", "media_number"),
    )

    movie_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("movie_items.id", ondelete="CASCADE"),
        nullable=False,
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

    item: Mapped[MovieItem] = relationship(back_populates="media")
