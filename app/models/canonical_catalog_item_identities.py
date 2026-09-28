from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CanonicalCatalogItemIdentity(Base):
    """A normalized edition identifier owned by one canonical Catalog Item."""

    __tablename__ = "catalog_item_identities"
    __table_args__ = (Index("idx_catalog_item_identity_item", "catalog_item_id"),)

    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    identifier_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    normalized_value: Mapped[str] = mapped_column(String(255), primary_key=True)
    catalog_item_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("catalog_items.id", ondelete="CASCADE"),
        nullable=False,
    )
