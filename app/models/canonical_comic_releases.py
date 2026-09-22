from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Index, Integer, String, Text, and_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import Base, ExternalProvider, TimestampMixin, UuidMixin
from app.models.canonical_comics import ComicIssue
from app.models.canonical_support import ExternalProviderId, Person


class ComicVariant(UuidMixin, TimestampMixin, Base):
    """Canonical Comic release under an Issue work."""

    __tablename__ = "comic_variants"
    __table_args__ = (
        Index("ix_comic_variants_issue_release_date", "issue_id", "release_date"),
        Index("ix_comic_variants_issue_barcode", "issue_id", "barcode"),
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_name: Mapped[str | None] = mapped_column(String(255), index=True)
    variant_type: Mapped[str | None] = mapped_column(String(64), index=True)
    cover_label: Mapped[str | None] = mapped_column(String(255))
    printing_number: Mapped[int | None] = mapped_column(Integer)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    imprint: Mapped[str | None] = mapped_column(String(255), index=True)
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    publication_date_parts: Mapped[str | None] = mapped_column(String(64))
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    release_date_parts: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    physical_format: Mapped[str | None] = mapped_column(String(64), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)

    issue: Mapped[ComicIssue] = relationship(back_populates="variants")
    provider_links: Mapped[list[ExternalProviderId]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == ComicVariant.id,
            ExternalProviderId.entity_type == "comic_variant",
        ),
        viewonly=True,
    )
    contributions: Mapped[list["ComicVariantContribution"]] = relationship(
        back_populates="variant", cascade="all, delete-orphan"
    )
    identifiers: Mapped[list["ComicVariantIdentifier"]] = relationship(
        back_populates="variant", cascade="all, delete-orphan"
    )


class ComicVariantContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_variant_contributions"
    __table_args__ = (
        Index("ix_comic_variant_contributions_variant_role", "variant_id", "role", "sequence"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_id: Mapped[str | None] = mapped_column(String(64), index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)

    variant: Mapped[ComicVariant] = relationship(back_populates="contributions")
    person: Mapped[Person] = relationship()


class ComicVariantIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_variant_identifiers"
    __table_args__ = (
        Index("ix_comic_variant_identifiers_variant_type_value", "variant_id", "identifier_type", "normalized_value"),
        Index("ix_comic_variant_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False), index=True
    )

    variant: Mapped[ComicVariant] = relationship(back_populates="identifiers")
