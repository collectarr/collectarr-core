from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import (
    Base,
    ItemKind,
    TimestampMixin,
    UuidMixin,
)
from app.models.canonical_support import (  # noqa: F401
    AdminAuditLog,
    AdminReleaseMediaMappingRule,
    Character,
    CharacterAppearance,
    ComicSeriesRelation,
    EntityAlias,
    EntityLink,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    ImageAsset,
    ImageCacheEntry,
    MangaSeriesRelation,
    MetadataProposal,
    Organization,
    Person,
    ProviderIngestJob,
    ProviderPayloadSnapshot,
    StoryArc,
    StoryArcItem,
    Tag,
)


class Item(UuidMixin, TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (
        Index("ix_items_kind_title", "kind", "title"),
        CheckConstraint(
            "runtime_minutes IS NULL OR runtime_minutes >= 0",
            name="ck_items_runtime_minutes_nonnegative",
        ),
        CheckConstraint(
            "page_count IS NULL OR page_count >= 0",
            name="ck_items_page_count_nonnegative",
        ),
    )

    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_title: Mapped[str | None] = mapped_column(String(255))
    localized_title: Mapped[str | None] = mapped_column(String(255))
    title_extension: Mapped[str | None] = mapped_column(String(255))
    item_number: Mapped[str | None] = mapped_column(String(64), index=True)
    sort_key: Mapped[str | None] = mapped_column(String(255), index=True)
    synopsis: Mapped[str | None] = mapped_column(Text)
    crossover: Mapped[str | None] = mapped_column(String(255))
    plot_summary: Mapped[str | None] = mapped_column(Text)
    plot_description: Mapped[str | None] = mapped_column(Text)
    release_type: Mapped[str | None] = mapped_column(String(64), index=True)
    season_number: Mapped[int | None] = mapped_column(Integer, index=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, index=True)
    air_date: Mapped[date | None] = mapped_column(Date, index=True)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    editions: Mapped[list["Edition"]] = relationship(back_populates="item")
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == Item.id,
            ExternalProviderId.entity_type == "item",
        ),
        viewonly=True,
    )
    organization_links: Mapped[list["EntityOrganization"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityOrganization.entity_id) == Item.id,
            EntityOrganization.entity_type == "item",
        ),
        viewonly=True,
    )
    creator_links: Mapped[list["EntityPerson"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityPerson.entity_id) == Item.id,
            EntityPerson.entity_type == "item",
        ),
        viewonly=True,
    )
    character_appearances: Mapped[list["CharacterAppearance"]] = relationship(
        back_populates="item"
    )
    story_arc_items: Mapped[list["StoryArcItem"]] = relationship(back_populates="item")
    alias_entries: Mapped[list["EntityAlias"]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        primaryjoin=lambda: and_(
            foreign(EntityAlias.entity_id) == Item.id,
            EntityAlias.entity_type == "item",
        ),
        order_by=lambda: (EntityAlias.position.asc(), EntityAlias.created_at.asc(), EntityAlias.id.asc()),
    )
    link_entries: Mapped[list["EntityLink"]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        primaryjoin=lambda: and_(
            foreign(EntityLink.entity_id) == Item.id,
            EntityLink.entity_type == "item",
        ),
        order_by=lambda: (EntityLink.position.asc(), EntityLink.created_at.asc(), EntityLink.id.asc()),
    )

    @property
    def search_aliases(self) -> list[str]:
        aliases: list[str] = []
        for row in list(self.__dict__.get("alias_entries") or []):
            alias = str(getattr(row, "alias", "") or "").strip()
            if alias:
                aliases.append(alias)
        return aliases

    @search_aliases.setter
    def search_aliases(self, values: list[str] | None) -> None:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in values or []:
            alias = str(raw or "").strip()
            if not alias:
                continue
            key = alias.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(alias)
        self.alias_entries = [
            EntityAlias(
                entity_type="item",
                alias=alias,
                normalized_alias=alias.casefold(),
                position=index,
            )
            for index, alias in enumerate(normalized)
        ]

    def _item_links_for_type(self, link_type: str) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in list(self.__dict__.get("link_entries") or []):
            if getattr(row, "link_type", None) != link_type:
                continue
            url = str(getattr(row, "url", "") or "").strip()
            if not url:
                continue
            entry: dict[str, Any] = {"url": url}
            for field in ("site", "name", "kind", "description"):
                value = str(getattr(row, field, "") or "").strip()
                if value:
                    entry[field] = value
            normalized.append(entry)
        return normalized

    def _set_item_links_for_type(self, link_type: str, values: list[dict[str, Any]] | None) -> None:
        kept = [
            row
            for row in list(self.__dict__.get("link_entries") or [])
            if getattr(row, "link_type", None) != link_type
        ]
        normalized_rows: list[EntityLink] = []
        for index, raw in enumerate(values or []):
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("url") or "").strip()
            if not url:
                continue
            normalized_rows.append(
                EntityLink(
                    entity_type="item",
                    link_type=link_type,
                    url=url,
                    site=str(raw.get("site") or "").strip() or None,
                    name=str(raw.get("name") or "").strip() or None,
                    kind=str(raw.get("kind") or "").strip() or None,
                    description=str(raw.get("description") or "").strip() or None,
                    position=index,
                )
            )
        self.link_entries = [*kept, *normalized_rows]

    @property
    def trailer_urls(self) -> list[dict[str, Any]]:
        return self._item_links_for_type("trailer")

    @trailer_urls.setter
    def trailer_urls(self, values: list[dict[str, Any]] | None) -> None:
        self._set_item_links_for_type("trailer", values)

    @property
    def external_links(self) -> list[dict[str, Any]]:
        return self._item_links_for_type("external")

    @external_links.setter
    def external_links(self, values: list[dict[str, Any]] | None) -> None:
        self._set_item_links_for_type("external", values)


class ReleaseStatus(UuidMixin, TimestampMixin, Base):
    __tablename__ = "release_statuses"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class PhysicalFormatRef(UuidMixin, TimestampMixin, Base):
    __tablename__ = "physical_format_refs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    media_family: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class Edition(UuidMixin, TimestampMixin, Base):
    __tablename__ = "editions"
    __table_args__ = (
        CheckConstraint("nr_discs IS NULL OR nr_discs >= 0", name="ck_editions_nr_discs_nonnegative"),
        Index("ix_editions_release_date", "release_date"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str | None] = mapped_column(String(100))
    physical_format: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("physical_format_refs.id", ondelete="SET NULL"),
        index=True,
    )
    physical_format_label: Mapped[str | None] = mapped_column(String(64))
    physical_format_media_family: Mapped[str | None] = mapped_column(String(64))
    physical_format_variant_type: Mapped[str | None] = mapped_column(String(64))
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    isbn: Mapped[str | None] = mapped_column(String(32), index=True)
    upc: Mapped[str | None] = mapped_column(String(32), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    imprint: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    series_group: Mapped[str | None] = mapped_column(String(255), index=True)
    age_rating: Mapped[str | None] = mapped_column(String(64), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100), index=True)
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    nr_discs: Mapped[int | None] = mapped_column(Integer)
    screen_ratio: Mapped[str | None] = mapped_column(String(64))
    audio_tracks: Mapped[str | None] = mapped_column(String(255))
    subtitles: Mapped[str | None] = mapped_column(String(255))
    layers: Mapped[str | None] = mapped_column(String(255))
    release_date: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    item: Mapped[Item] = relationship(back_populates="editions")
    variants: Mapped[list["Variant"]] = relationship(back_populates="edition")
    physical_format_ref: Mapped[PhysicalFormatRef | None] = relationship()

class MetadataTaxonomy(UuidMixin, TimestampMixin, Base):
    __tablename__ = "metadata_taxonomies"
    __table_args__ = (
        CheckConstraint(
            "category IN ('genre', 'platform')",
            name="ck_metadata_taxonomies_category_valid",
        ),
    )

    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class Variant(UuidMixin, TimestampMixin, Base):
    __tablename__ = "variants"
    __table_args__ = (
        CheckConstraint(
            "cover_price_cents IS NULL OR cover_price_cents >= 0",
            name="ck_variants_cover_price_cents_nonnegative",
        ),
        Index(
            "uq_variants_primary_per_edition",
            "edition_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editions.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_type: Mapped[str | None] = mapped_column(String(64), index=True)
    physical_format: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("physical_format_refs.id", ondelete="SET NULL"),
        index=True,
    )
    physical_format_label: Mapped[str | None] = mapped_column(String(64))
    physical_format_media_family: Mapped[str | None] = mapped_column(String(64))
    physical_format_variant_type: Mapped[str | None] = mapped_column(String(64))
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(32), index=True)
    isbn: Mapped[str | None] = mapped_column(String(32), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    platform: Mapped[str | None] = mapped_column(String(64), index=True)
    cover_price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    thumbnail_image_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_image_url: Mapped[str | None] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    edition: Mapped[Edition] = relationship(back_populates="variants")
    physical_format_ref: Mapped[PhysicalFormatRef | None] = relationship()


class BundleRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "bundle_releases"
    __table_args__ = (
        Index("ix_bundle_releases_kind_bundle_type", "kind", "bundle_type"),
        Index("ix_bundle_releases_format_region", "format", "region"),
    )

    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    bundle_type: Mapped[str | None] = mapped_column(String(64), index=True)
    format: Mapped[str | None] = mapped_column(String(64), index=True)
    variant_type: Mapped[str | None] = mapped_column(String(64), index=True)
    packaging_type: Mapped[str | None] = mapped_column(String(64), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    language: Mapped[str | None] = mapped_column(String(32), index=True)
    publisher: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(32), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    thumbnail_image_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_image_url: Mapped[str | None] = mapped_column(String(1024))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    components: Mapped[list["BundleReleaseComponent"]] = relationship(
        back_populates="bundle_release", cascade="all, delete-orphan"
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == BundleRelease.id,
            ExternalProviderId.entity_type == "bundle_release",
        ),
        viewonly=True,
    )
class BundleReleaseComponent(UuidMixin, TimestampMixin, Base):
    __tablename__ = "bundle_release_components"
    __table_args__ = (
        UniqueConstraint(
            "bundle_release_id",
            "entity_type",
            "entity_id",
            "role",
            "disc_number",
            "sequence_number",
            name="uq_bundle_release_component_membership",
        ),
        Index(
            "ix_bundle_release_components_bundle_sequence",
            "bundle_release_id",
            "disc_number",
            "sequence_number",
        ),
        Index("ix_bundle_release_components_entity", "entity_type", "entity_id"),
    )

    bundle_release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bundle_releases.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    disc_number: Mapped[int | None] = mapped_column(Integer, index=True)
    disc_label: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    bundle_release: Mapped[BundleRelease] = relationship(back_populates="components")
