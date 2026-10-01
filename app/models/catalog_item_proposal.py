"""Source-neutral user proposals for new catalog items."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ItemKind, TimestampMixin, UuidMixin


class CatalogItemProposal(UuidMixin, TimestampMixin, Base):
    """A user-submitted Add/Edit form payload waiting for catalog review."""

    __tablename__ = "catalog_item_proposals"

    kind: Mapped[ItemKind] = mapped_column(
        Enum(ItemKind, name="item_kind", create_type=False), nullable=False, index=True
    )
    catalog_item: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    submitted_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    review_note: Mapped[str | None] = mapped_column(String(2000))
