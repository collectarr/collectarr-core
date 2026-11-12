"""Game-level catalog records and their concrete media editions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidMixin


class GameItem(UuidMixin, TimestampMixin, Base):
    """A game, or an independently editable edition linked to its game."""

    __tablename__ = "game_items"
    __table_args__ = (
        CheckConstraint("parent_game_id IS NULL OR parent_game_id <> id", name="ck_game_items_not_own_parent"),
        Index("ix_game_items_title", "title"),
        Index(
            "ix_game_items_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_game_items_sort_key", "sort_key"),
        Index(
            "ix_game_items_sort_key_trgm",
            "sort_key",
            postgresql_using="gin",
            postgresql_ops={"sort_key": "gin_trgm_ops"},
        ),
        Index("ix_game_items_barcode", "barcode"),
        Index("ix_game_items_catalog_number", "catalog_number"),
        Index(
            "ix_game_items_details_gin",
            "details",
            postgresql_using="gin",
            postgresql_ops={"details": "jsonb_path_ops"},
        ),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_game_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("game_items.id", name="fk_game_items_parent_game_id", ondelete="RESTRICT"),
        index=True,
    )
    sort_key: Mapped[str | None] = mapped_column(String(255))
    barcode: Mapped[str | None] = mapped_column(String(100))
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}

    @property
    def game_id(self) -> UUID:
        return self.parent_game_id or self.id

    @property
    def media_id(self) -> UUID | None:
        return self.id if self.parent_game_id is not None else None
