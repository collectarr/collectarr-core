"""Music catalog items with contained disc/track documents."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Boolean, Date, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.models.base import Base, TimestampMixin, UuidMixin


class MusicItem(UuidMixin, TimestampMixin, Base):
    """One concrete album edition, with no release-group parent."""

    __tablename__ = "music_items"
    __table_args__ = (
        Index("ix_music_items_title", "title"),
        Index(
            "ix_music_items_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_music_items_sort_title", "sort_title"),
        Index(
            "ix_music_items_sort_title_trgm",
            "sort_title",
            postgresql_using="gin",
            postgresql_ops={"sort_title": "gin_trgm_ops"},
        ),
        Index(
            "ix_music_items_artist_trgm",
            "artist",
            postgresql_using="gin",
            postgresql_ops={"artist": "gin_trgm_ops"},
        ),
        Index(
            "ix_music_items_label_trgm",
            "label",
            postgresql_using="gin",
            postgresql_ops={"label": "gin_trgm_ops"},
        ),
        Index(
            "ix_music_items_subtitle_trgm",
            "subtitle",
            postgresql_using="gin",
            postgresql_ops={"subtitle": "gin_trgm_ops"},
        ),
        Index("ix_music_items_barcode", "barcode"),
        Index("ix_music_items_catalog_number", "catalog_number"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_title: Mapped[str | None] = mapped_column(String(255))
    subtitle: Mapped[str | None] = mapped_column(String(500))
    artist: Mapped[str | None] = mapped_column(String(500))
    artist_credits: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    original_release_date: Mapped[date | None] = mapped_column(Date)
    original_release_date_parts: Mapped[dict[str, int] | str | None] = mapped_column(JSONB)
    recording_date: Mapped[date | None] = mapped_column(Date)
    recording_date_parts: Mapped[dict[str, int] | str | None] = mapped_column(JSONB)
    release_date: Mapped[date | None] = mapped_column(Date)
    release_date_parts: Mapped[dict[str, int] | str | None] = mapped_column(JSONB)
    label: Mapped[str | None] = mapped_column(String(255))
    format: Mapped[str | None] = mapped_column(String(100))
    barcode: Mapped[str | None] = mapped_column(String(100))
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    genres: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    packaging: Mapped[str | None] = mapped_column(String(100))
    studios: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    country: Mapped[str | None] = mapped_column(String(100))
    is_live: Mapped[bool | None] = mapped_column(Boolean)
    sound_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    vinyl_color: Mapped[str | None] = mapped_column(String(100))
    vinyl_weight: Mapped[str | None] = mapped_column(String(100))
    rpm: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[str | None] = mapped_column(Text)
    spars: Mapped[str | None] = mapped_column(String(50))
    box_set: Mapped[str | None] = mapped_column(String(255))
    composers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    conductors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    choruses: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    compositions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    orchestras: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    songwriters: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    producers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    engineers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    musicians: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    external_links: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    back_cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    thumbnail_image_url: Mapped[str | None] = mapped_column(String(2048))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}

    discs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    @validates("discs")
    def validate_discs(self, _key: str, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate and replace the full document so SQLAlchemy tracks edits."""
        from app.schemas.catalog_music_item import normalize_music_discs

        return normalize_music_discs(value)
