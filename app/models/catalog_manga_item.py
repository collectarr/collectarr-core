"""Flattened Manga Catalog Items."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidMixin


class MangaItem(UuidMixin, TimestampMixin, Base):
    """One concrete Manga volume edition without an editable Work parent."""

    __tablename__ = "manga_items"
    __table_args__ = (
        Index("ix_manga_items_title", "title"),
        Index(
            "ix_manga_items_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_manga_items_sort_key", "sort_key"),
        Index(
            "ix_manga_items_sort_key_trgm",
            "sort_key",
            postgresql_using="gin",
            postgresql_ops={"sort_key": "gin_trgm_ops"},
        ),
        Index("ix_manga_items_barcode", "barcode"),
        Index("ix_manga_items_catalog_number", "catalog_number"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_key: Mapped[str | None] = mapped_column(String(255))
    barcode: Mapped[str | None] = mapped_column(String(100))
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}

    identifiers: Mapped[list["MangaItemIdentifier"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="MangaItemIdentifier.identifier_type",
    )


class MangaItemIdentifier(UuidMixin, TimestampMixin, Base):
    """A source-neutral canonical identifier attached to one Manga item."""

    __tablename__ = "manga_item_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "manga_item_id",
            "identifier_type",
            "normalized_value",
            name="uq_manga_item_identifier_normalized",
        ),
        Index("ix_manga_item_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    manga_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("manga_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    item: Mapped[MangaItem] = relationship(back_populates="identifiers")
