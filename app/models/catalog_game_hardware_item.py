"""Canonical game hardware editions; device serial numbers are personal data."""

from typing import Any

from sqlalchemy import Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidMixin


class GameHardwareItem(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_hardware_items"
    __table_args__ = (
        Index("ix_game_hardware_items_title", "title"),
        Index("ix_game_hardware_items_barcode", "barcode"),
        Index("ix_game_hardware_items_sort_key", "sort_key"),
        Index("ix_game_hardware_items_details_gin", "details", postgresql_using="gin"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_key: Mapped[str | None] = mapped_column(String(255))
    barcode: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}
