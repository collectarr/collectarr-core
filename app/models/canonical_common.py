from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import (
    Base,
    ExternalProvider,
    ItemKind,
    TimestampMixin,
    UuidMixin,
)
from app.models.canonical_support import (  # noqa: F401
    AdminAuditLog,
    AdminReleaseMediaMappingRule,
    Character,
    CharacterAppearance,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    ImageAsset,
    ImageCacheEntry,
    MetadataProposal,
    Organization,
    Person,
    ProviderIngestJob,
    ProviderPayloadSnapshot,
    ComicSeriesRelation,
    MangaSeriesRelation,
    SeriesRelation,
    StoryArc,
    StoryArcItem,
    Tag,
)

class Franchise(UuidMixin, TimestampMixin, Base):
    __tablename__ = "franchises"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Series(UuidMixin, TimestampMixin, Base):
    __tablename__ = "series"

    franchise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("franchises.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    original_title: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    country: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    franchise: Mapped[Franchise | None] = relationship()
    volumes: Mapped[list["Volume"]] = relationship(back_populates="series")
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == Series.id,
            ExternalProviderId.entity_type == "series",
        ),
        viewonly=True,
    )


class Volume(UuidMixin, TimestampMixin, Base):
    __tablename__ = "volumes"

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    volume_number: Mapped[float | None] = mapped_column(Float)
    start_year: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[Series] = relationship(back_populates="volumes")
    items: Mapped[list["Item"]] = relationship(back_populates="volume")
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == Volume.id,
            ExternalProviderId.entity_type == "volume",
        ),
        viewonly=True,
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

    volume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("volumes.id", ondelete="SET NULL"), index=True
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

    volume: Mapped[Volume | None] = relationship(back_populates="items")
    editions: Mapped[list["Edition"]] = relationship(back_populates="item")
    primary_bundle_releases: Mapped[list["BundleRelease"]] = relationship(
        back_populates="primary_item",
        foreign_keys="BundleRelease.primary_item_id",
    )
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
    kind_metadata: Mapped["ItemKindMetadata | None"] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        uselist=False,
    )
    alias_entries: Mapped[list["ItemAlias"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by=lambda: (ItemAlias.position.asc(), ItemAlias.created_at.asc(), ItemAlias.id.asc()),
    )
    link_entries: Mapped[list["ItemLink"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by=lambda: (ItemLink.position.asc(), ItemLink.created_at.asc(), ItemLink.id.asc()),
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
            ItemAlias(
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
        normalized_rows: list[ItemLink] = []
        for index, raw in enumerate(values or []):
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("url") or "").strip()
            if not url:
                continue
            normalized_rows.append(
                ItemLink(
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


class ItemAlias(UuidMixin, TimestampMixin, Base):
    __tablename__ = "item_aliases"
    __table_args__ = (
        UniqueConstraint("item_id", "normalized_alias", name="uq_item_aliases_item_normalized_alias"),
        Index("ix_item_aliases_item_position", "item_id", "position"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    item: Mapped[Item] = relationship(back_populates="alias_entries")


class ItemLink(UuidMixin, TimestampMixin, Base):
    __tablename__ = "item_links"
    __table_args__ = (
        CheckConstraint(
            "link_type IN ('trailer', 'external')",
            name="ck_item_links_link_type_valid",
        ),
        Index("ix_item_links_item_type_position", "item_id", "link_type", "position"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    link_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    site: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    kind: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    item: Mapped[Item] = relationship(back_populates="link_entries")


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

class ItemKindMetadata(UuidMixin, TimestampMixin, Base):
    __tablename__ = "item_kind_metadata"
    __table_args__ = (
        UniqueConstraint("item_id", name="uq_item_kind_metadata_item_id"),
        Index("ix_item_kind_metadata_kind", "kind"),
    )
    __mapper_args__ = {"polymorphic_on": "kind", "with_polymorphic": "*"}

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    audience_rating: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    item: Mapped[Item] = relationship(back_populates="kind_metadata")
    taxonomy_links: Mapped[list["ItemKindMetadataTaxonomy"]] = relationship(
        back_populates="item_kind_metadata",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by=lambda: (
            ItemKindMetadataTaxonomy.category.asc(),
            ItemKindMetadataTaxonomy.position.asc(),
            ItemKindMetadataTaxonomy.created_at.asc(),
            ItemKindMetadataTaxonomy.id.asc(),
        ),
    )

    def _metadata_values(self) -> dict[str, Any]:
        return dict(self.metadata_json or {})

    def _taxonomy_values(self, category: str) -> list[str]:
        values: list[str] = []
        for row in list(self.__dict__.get("taxonomy_links") or []):
            if getattr(row, "category", None) != category:
                continue
            taxonomy = getattr(row, "taxonomy", None)
            name = str(getattr(taxonomy, "name", "") or "").strip()
            if name:
                values.append(name)
        return values

    @property
    def genres(self) -> list[str]:
        return self._taxonomy_values("genre")

    @genres.setter
    def genres(self, values: list[str] | None) -> None:
        self._set_taxonomy_values("genre", values)

    @property
    def platforms(self) -> list[str]:
        return self._taxonomy_values("platform")

    @platforms.setter
    def platforms(self, values: list[str] | None) -> None:
        self._set_taxonomy_values("platform", values)

    @property
    def track_count(self) -> int | None:
        value = self._metadata_values().get("track_count")
        return value if isinstance(value, int) else None

    @track_count.setter
    def track_count(self, value: int | None) -> None:
        self._set_scalar_value("track_count", value)

    @property
    def tracks(self) -> list[dict[str, Any]]:
        values = self._metadata_values().get("tracks")
        if not isinstance(values, list):
            return []
        return [dict(entry) for entry in values if isinstance(entry, Mapping)]

    @tracks.setter
    def tracks(self, values: list[Mapping[str, Any]] | None) -> None:
        cleaned: list[dict[str, Any]] = []
        for raw in values or []:
            title = str(raw.get("title") or "").strip()
            if not title:
                continue
            entry: dict[str, Any] = {"title": title}
            for key in ("position", "duration_seconds", "artist", "disc_number"):
                value = raw.get(key)
                if value is not None:
                    entry[key] = value
            cleaned.append(entry)
        self._set_list_value("tracks", cleaned)

    @property
    def color(self) -> str | None:
        value = self._metadata_values().get("color")
        return value if isinstance(value, str) and value.strip() else None

    @color.setter
    def color(self, value: str | None) -> None:
        self._set_scalar_value("color", value)

    def _set_taxonomy_values(self, category: str, values: list[str] | None) -> None:
        deduped: list[str] = []
        seen: set[str] = set()
        for raw in values or []:
            text = str(raw or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(text)
        existing_other_categories = [
            row
            for row in list(self.__dict__.get("taxonomy_links") or [])
            if getattr(row, "category", None) != category
        ]
        self.taxonomy_links = [
            *existing_other_categories,
            *[
                ItemKindMetadataTaxonomy(
                    category=category,
                    position=index,
                    taxonomy=MetadataTaxonomy(
                        category=category,
                        name=text,
                        normalized_name=text.casefold(),
                    ),
                )
                for index, text in enumerate(deduped)
            ],
        ]

    def _set_scalar_value(self, key: str, value: Any) -> None:
        metadata = self._metadata_values()
        if value is None or value == "":
            metadata.pop(key, None)
        else:
            metadata[key] = value
        self.metadata_json = metadata or None

    def _set_list_value(self, key: str, values: list[Any] | None) -> None:
        metadata = self._metadata_values()
        if key == "tracks":
            cleaned_tracks: list[dict[str, Any]] = []
            for raw in values or []:
                if not isinstance(raw, Mapping):
                    continue
                title = str(raw.get("title") or "").strip()
                if not title:
                    continue
                entry: dict[str, Any] = {"title": title}
                for field_name in ("position", "duration_seconds", "artist", "disc_number"):
                    field_value = raw.get(field_name)
                    if field_value is not None:
                        entry[field_name] = field_value
                cleaned_tracks.append(entry)
            if cleaned_tracks:
                metadata[key] = cleaned_tracks
            else:
                metadata.pop(key, None)
            self.metadata_json = metadata or None
            return

        deduped: list[str] = []
        seen: set[str] = set()
        for raw in values or []:
            text = str(raw or "").strip()
            if not text:
                continue
            normalized = text.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(text)
        if deduped:
            metadata[key] = deduped
        else:
            metadata.pop(key, None)
        self.metadata_json = metadata or None


class ItemKindMetadataAnime(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.anime}


class ItemKindMetadataBoardGame(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.boardgame}


class ItemKindMetadataBook(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.book}


class ItemKindMetadataCollection(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.collection}


class ItemKindMetadataComic(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.comic}


class ItemKindMetadataGame(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.game}


class ItemKindMetadataManga(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.manga}


class ItemKindMetadataMovie(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.movie}


class ItemKindMetadataMusic(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.music}


class ItemKindMetadataTv(ItemKindMetadata):
    __mapper_args__ = {"polymorphic_identity": ItemKind.tv}


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


class ItemKindMetadataTaxonomy(UuidMixin, TimestampMixin, Base):
    __tablename__ = "item_kind_metadata_taxonomies"
    __table_args__ = (
        UniqueConstraint(
            "item_kind_metadata_id",
            "taxonomy_id",
            "category",
            name="uq_item_kind_metadata_taxonomy_link",
        ),
        Index(
            "ix_item_kind_metadata_taxonomies_owner_category_position",
            "item_kind_metadata_id",
            "category",
            "position",
        ),
    )

    item_kind_metadata_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("item_kind_metadata.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    taxonomy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata_taxonomies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    item_kind_metadata: Mapped[ItemKindMetadata] = relationship(back_populates="taxonomy_links")
    taxonomy: Mapped[MetadataTaxonomy] = relationship(lazy="joined")


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
        Index("ix_bundle_releases_series_release_date", "series_id", "release_date"),
        Index("ix_bundle_releases_format_region", "format", "region"),
    )

    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    bundle_type: Mapped[str | None] = mapped_column(String(64), index=True)
    franchise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("franchises.id", ondelete="SET NULL"), index=True
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="SET NULL"), index=True
    )
    volume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("volumes.id", ondelete="SET NULL"), index=True
    )
    primary_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="SET NULL"), index=True
    )
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

    franchise: Mapped[Franchise | None] = relationship()
    series: Mapped[Series | None] = relationship()
    volume: Mapped[Volume | None] = relationship()
    primary_item: Mapped[Item | None] = relationship(
        back_populates="primary_bundle_releases",
        foreign_keys=[primary_item_id],
    )
    items: Mapped[list["BundleReleaseItem"]] = relationship(
        back_populates="bundle_release", cascade="all, delete-orphan"
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == BundleRelease.id,
            ExternalProviderId.entity_type == "bundle_release",
        ),
        viewonly=True,
    )


class BundleReleaseItem(UuidMixin, TimestampMixin, Base):
    __tablename__ = "bundle_release_items"
    __table_args__ = (
        UniqueConstraint(
            "bundle_release_id",
            "item_id",
            "role",
            "disc_number",
            "sequence_number",
            name="uq_bundle_release_item_membership",
        ),
        Index("ix_bundle_release_items_bundle_sequence", "bundle_release_id", "disc_number", "sequence_number"),
    )

    bundle_release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bundle_releases.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    disc_number: Mapped[int | None] = mapped_column(Integer, index=True)
    disc_label: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    bundle_release: Mapped[BundleRelease] = relationship(back_populates="items")
    item: Mapped[Item] = relationship()
