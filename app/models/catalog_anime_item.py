"""Flattened Anime Catalog Items with contained media and episode rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

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
        Index(
            "ix_anime_items_details_gin",
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
