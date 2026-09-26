from __future__ import annotations

from sqlalchemy import JSON, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidMixin


class CanonicalCatalogItem(UuidMixin, TimestampMixin, Base):
    """One concrete, source-neutral collectible catalog item for any kind."""

    __tablename__ = "catalog_items"
    __table_args__ = (
        Index("idx_catalog_items_kind_title", "kind", "title"),
        Index("idx_catalog_items_sort_title", "kind", "sort_title"),
        Index("idx_catalog_items_identifier_search", "identifier_search"),
    )

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_title: Mapped[str | None] = mapped_column(String(500))
    identifier_search: Mapped[str] = mapped_column(Text, nullable=False, default="")
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
