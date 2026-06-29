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


class BookWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_works"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(16), index=True)
    original_publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    first_publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    editions: Mapped[list["BookEdition"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["BookContribution"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    series_memberships: Mapped[list["BookSeriesMembership"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )


class BookSeries(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_series"

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

    works: Mapped[list["BookSeriesMembership"]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == BookSeries.id,
            ExternalProviderId.entity_type == "book_series",
        ),
        viewonly=True,
    )


class BookEdition(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_editions"
    __table_args__ = (
        Index("ix_book_editions_work_publication", "work_id", "publication_date"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_title: Mapped[str | None] = mapped_column(String(255))
    edition_statement: Mapped[str | None] = mapped_column(String(255))
    format: Mapped[str | None] = mapped_column(String(100), index=True)
    binding: Mapped[str | None] = mapped_column(String(100), index=True)
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    imprint: Mapped[str | None] = mapped_column(String(255), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    audio_length_minutes: Mapped[int | None] = mapped_column(Integer)
    age_rating: Mapped[str | None] = mapped_column(String(64), index=True)
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BookWork] = relationship(back_populates="editions")
    printings: Mapped[list["BookPrinting"]] = relationship(
        back_populates="edition",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["BookContribution"]] = relationship(
        back_populates="edition",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["BookIdentifier"]] = relationship(
        back_populates="edition",
        cascade="all, delete-orphan",
    )


class BookPrinting(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_printings"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    printing_number: Mapped[int | None] = mapped_column(Integer, index=True)
    printing_statement: Mapped[str | None] = mapped_column(String(255))
    print_run: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    edition: Mapped[BookEdition] = relationship(back_populates="printings")


class BookContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_contributions"
    __table_args__ = (
        CheckConstraint(
            "((work_id IS NOT NULL AND edition_id IS NULL) OR (work_id IS NULL AND edition_id IS NOT NULL))",
            name="ck_book_contributions_work_xor_edition",
        ),
        Index(
            "ix_book_contributions_work_role_sequence",
            "work_id",
            "role",
            "sequence",
        ),
        Index(
            "ix_book_contributions_edition_role_sequence",
            "edition_id",
            "role",
            "sequence",
        ),
    )

    work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_works.id", ondelete="CASCADE"), index=True
    )
    edition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_editions.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BookWork | None] = relationship(back_populates="contributions")
    edition: Mapped[BookEdition | None] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class BookIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "edition_id",
            "identifier_type",
            "normalized_value",
            name="uq_book_identifiers_edition_type_normalized",
        ),
        Index("ix_book_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    edition: Mapped[BookEdition] = relationship(back_populates="identifiers")


class BookSeriesMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "book_series_memberships"
    __table_args__ = (
        UniqueConstraint("work_id", "series_id", name="uq_book_series_memberships_work_series"),
        Index("ix_book_series_memberships_series_sequence", "series_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[float | None] = mapped_column(Float)
    display_number: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BookWork] = relationship(back_populates="series_memberships")
    series: Mapped[BookSeries] = relationship(back_populates="works")


class ComicWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_works"

    volume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_volumes.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(16), index=True)
    first_publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    volume: Mapped["ComicVolume | None"] = relationship(back_populates="works")
    issues: Mapped[list["ComicIssue"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["ComicContribution"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    series_memberships: Mapped[list["ComicSeriesMembership"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )


class ComicVolume(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_volumes"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    original_title: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    start_year: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    country: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    works: Mapped[list["ComicWork"]] = relationship(back_populates="volume")
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == ComicVolume.id,
            ExternalProviderId.entity_type == "comic_volume",
        ),
        viewonly=True,
    )


class ComicIssue(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_issues"
    __table_args__ = (
        Index("ix_comic_issues_work_issue_number", "work_id", "issue_number"),
        Index("ix_comic_issues_work_publication", "work_id", "publication_date"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issue_number: Mapped[str | None] = mapped_column(String(64), index=True)
    display_title: Mapped[str | None] = mapped_column(String(255))
    publication_date: Mapped[date | None] = mapped_column(Date, index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    imprint: Mapped[str | None] = mapped_column(String(255), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    cover_price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(8))
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[ComicWork] = relationship(back_populates="issues")
    contributions: Mapped[list["ComicContribution"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["ComicIdentifier"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    story_arc_memberships: Mapped[list["ComicStoryArcMembership"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    character_appearances: Mapped[list["ComicCharacterAppearance"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )


class ComicContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_contributions"
    __table_args__ = (
        CheckConstraint(
            "((work_id IS NOT NULL AND issue_id IS NULL) OR (work_id IS NULL AND issue_id IS NOT NULL))",
            name="ck_comic_contributions_work_xor_issue",
        ),
        Index("ix_comic_contributions_work_role_sequence", "work_id", "role", "sequence"),
        Index("ix_comic_contributions_issue_role_sequence", "issue_id", "role", "sequence"),
    )

    work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_works.id", ondelete="CASCADE"), index=True
    )
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_issues.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[ComicWork | None] = relationship(back_populates="contributions")
    issue: Mapped[ComicIssue | None] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class ComicIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "issue_id",
            "identifier_type",
            "normalized_value",
            name="uq_comic_identifiers_issue_type_normalized",
        ),
        Index("ix_comic_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    issue: Mapped[ComicIssue] = relationship(back_populates="identifiers")


class ComicStoryArcMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_story_arc_memberships"
    __table_args__ = (
        UniqueConstraint("issue_id", "story_arc_id", name="uq_comic_story_arc_memberships_issue_arc"),
        Index("ix_comic_story_arc_memberships_issue_ordinal", "issue_id", "ordinal"),
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    story_arc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_arcs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    issue: Mapped[ComicIssue] = relationship(back_populates="story_arc_memberships")
    story_arc: Mapped["StoryArc"] = relationship()


class ComicCharacterAppearance(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_character_appearances"
    __table_args__ = (
        UniqueConstraint(
            "issue_id",
            "character_id",
            "role",
            name="uq_comic_character_appearances_issue_character_role",
        ),
        Index("ix_comic_character_appearances_issue_role", "issue_id", "role"),
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="featured", index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    issue: Mapped[ComicIssue] = relationship(back_populates="character_appearances")
    character: Mapped["Character"] = relationship()


class ComicSeriesMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "comic_series_memberships"
    __table_args__ = (
        UniqueConstraint("work_id", "series_id", name="uq_comic_series_memberships_work_series"),
        Index("ix_comic_series_memberships_series_sequence", "series_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comic_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[float | None] = mapped_column(Float)
    display_number: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[ComicWork] = relationship(back_populates="series_memberships")
    series: Mapped[Series] = relationship()


# ========================
# TV v1 Schema
# ========================


class TVRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_releases"
    __table_args__ = (
        Index("idx_tv_releases_sort_title", "sort_title"),
        Index("idx_tv_releases_sku", "sku"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    media_count: Mapped[int | None] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(64), nullable=False)
    region_code: Mapped[str | None] = mapped_column(String(2))
    release_date: Mapped[date | None] = mapped_column(Date)
    publisher: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    case_type: Mapped[str | None] = mapped_column(String(64))
    episode_count: Mapped[int | None] = mapped_column(Integer)
    season_count: Mapped[int | None] = mapped_column(Integer)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    language_audio: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    language_subtitles: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    content_rating: Mapped[str | None] = mapped_column(String(64))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    media: Mapped[list["TVReleaseMedia"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    episodes: Mapped[list["TVEpisode"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["TVReleaseContribution"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["TVReleaseIdentifier"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )


class TVReleaseMedia(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_release_media"
    __table_args__ = (
        UniqueConstraint("release_id", "media_number", name="unique_tv_release_media"),
        Index("idx_tv_release_media_release_id", "release_id"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_number: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    episode_count: Mapped[int | None] = mapped_column(Integer)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    region_code: Mapped[str | None] = mapped_column(String(2))
    encoding: Mapped[str | None] = mapped_column(String(64))
    aspect_ratio: Mapped[str | None] = mapped_column(String(16))
    frame_rate: Mapped[str | None] = mapped_column(String(16))
    bit_depth: Mapped[str | None] = mapped_column(String(16))
    resolution: Mapped[str | None] = mapped_column(String(16))
    hdr_format: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[TVRelease] = relationship(back_populates="media")
    episodes: Mapped[list["TVEpisode"]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )


class TVEpisode(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_episodes"
    __table_args__ = (
        UniqueConstraint("release_id", "season_number", "episode_number", name="unique_tv_episode"),
        Index("idx_tv_episodes_release_id", "release_id"),
        Index("idx_tv_episodes_media_id", "media_id"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_release_media.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_title: Mapped[str] = mapped_column(String(255), nullable=False)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    original_air_date: Mapped[date | None] = mapped_column(Date)
    still_url: Mapped[str | None] = mapped_column(String(2048))
    still_key: Mapped[str | None] = mapped_column(String(512))
    audio_tracks: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    subtitle_tracks: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[TVRelease] = relationship(back_populates="episodes")
    media: Mapped[TVReleaseMedia] = relationship(back_populates="episodes")


class TVReleaseContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_release_contributions"
    __table_args__ = (
        UniqueConstraint("release_id", "person_id", "role", name="unique_tv_release_contribution"),
        Index("idx_tv_release_contributions_release_id", "release_id"),
        Index("idx_tv_release_contributions_person_id", "person_id"),
        Index("idx_tv_release_contributions_role", "release_id", "role"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    character_name: Mapped[str | None] = mapped_column(String(255))
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[TVRelease] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class TVReleaseIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tv_release_identifiers"
    __table_args__ = (
        UniqueConstraint("release_id", "identifier_type", "value", name="unique_tv_release_identifier"),
        Index("idx_tv_release_identifiers_release_id", "release_id"),
        Index("idx_tv_release_identifiers_type_value", "identifier_type", "value"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tv_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[TVRelease] = relationship(back_populates="identifiers")


# ========================
# Music v1 Schema
# ========================


class MusicRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_releases"
    __table_args__ = (
        Index("idx_music_releases_barcode", "barcode"),
        Index("idx_music_releases_created_at", "created_at"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    release_type: Mapped[str | None] = mapped_column(String(64))
    release_status: Mapped[str | None] = mapped_column(String(50))
    release_date: Mapped[date | None] = mapped_column(Date)
    recording_date: Mapped[date | None] = mapped_column(Date)
    media_count: Mapped[int | None] = mapped_column(Integer)
    track_count: Mapped[int | None] = mapped_column(Integer)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    publisher: Mapped[str | None] = mapped_column(String(255))
    studio: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(2))
    language: Mapped[str | None] = mapped_column(String(2))
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100))
    audience_rating: Mapped[float | None] = mapped_column(Float)
    rating_count: Mapped[int | None] = mapped_column(Integer)
    extras: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    media: Mapped[list["MusicMedia"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["MusicReleaseContribution"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["MusicReleaseIdentifier"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )


class MusicMedia(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_media"
    __table_args__ = (
        UniqueConstraint("release_id", "media_number", name="unique_music_media"),
        Index("idx_music_media_release_id", "release_id"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_number: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))
    track_count: Mapped[int | None] = mapped_column(Integer)
    packaging: Mapped[str | None] = mapped_column(String(100))
    media_condition: Mapped[str | None] = mapped_column(String(100))
    sound_type: Mapped[str | None] = mapped_column(String(50))
    vinyl_color: Mapped[str | None] = mapped_column(String(100))
    vinyl_weight: Mapped[str | None] = mapped_column(String(100))
    rpm: Mapped[int | None] = mapped_column(Integer)
    spars: Mapped[str | None] = mapped_column(String(50))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MusicRelease] = relationship(back_populates="media")
    tracks: Mapped[list["MusicTrack"]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )


class MusicTrack(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_tracks"
    __table_args__ = (
        UniqueConstraint("media_id", "position", name="unique_music_track"),
        Index("idx_music_tracks_release_id", "release_id"),
    )

    media_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_media.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    instrument: Mapped[str | None] = mapped_column(String(100))
    composition: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    media: Mapped[MusicMedia] = relationship(back_populates="tracks")
    release: Mapped[MusicRelease] = relationship()


class MusicReleaseContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_release_contributions"
    __table_args__ = (
        UniqueConstraint("release_id", "person_id", "role", name="unique_music_release_contribution"),
        Index("idx_music_release_contributions_release_id", "release_id"),
        Index("idx_music_release_contributions_role", "release_id", "role"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MusicRelease] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class MusicReleaseIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "music_release_identifiers"
    __table_args__ = (
        UniqueConstraint("release_id", "identifier_type", "value", name="unique_music_release_identifier"),
        Index("idx_music_release_identifiers_release_id", "release_id"),
        Index("idx_music_release_identifiers_type_value", "identifier_type", "value"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("music_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MusicRelease] = relationship(back_populates="identifiers")


# ========================
# Movie v1 Schema
# ========================


class MovieWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_works"
    __table_args__ = (
        Index("idx_movie_works_created_at", "created_at"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(2))
    original_title: Mapped[str | None] = mapped_column(String(255))
    original_release_date: Mapped[date | None] = mapped_column(Date)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(64))
    budget_usd: Mapped[int | None] = mapped_column(Integer)
    revenue_usd: Mapped[int | None] = mapped_column(Integer)
    age_rating: Mapped[str | None] = mapped_column(String(20))
    audience_rating: Mapped[str | None] = mapped_column(String(50))
    rating_count: Mapped[int | None] = mapped_column(Integer)
    poster_image_url: Mapped[str | None] = mapped_column(String(2048))
    poster_image_key: Mapped[str | None] = mapped_column(String(512))
    backdrop_image_url: Mapped[str | None] = mapped_column(String(2048))
    backdrop_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    releases: Mapped[list["MovieRelease"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    contributions: Mapped[list["MovieWorkContribution"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["MovieWorkIdentifier"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )


class MovieRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_releases"
    __table_args__ = (
        UniqueConstraint("work_id", "region_code", "format", name="unique_movie_release"),
        Index("idx_movie_releases_work_id", "work_id"),
        Index("idx_movie_releases_barcode", "barcode"),
        Index("idx_movie_releases_created_at", "created_at"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movie_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    format: Mapped[str] = mapped_column(String(64), nullable=False)
    region_code: Mapped[str | None] = mapped_column(String(2))
    release_date: Mapped[date | None] = mapped_column(Date)
    release_type: Mapped[str | None] = mapped_column(String(64))
    certification: Mapped[str | None] = mapped_column(String(64))
    publisher: Mapped[str | None] = mapped_column(String(255))
    distributor: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    media_count: Mapped[int | None] = mapped_column(Integer)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    language_audio: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    language_subtitles: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(String))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    work: Mapped[MovieWork] = relationship(back_populates="releases")
    media: Mapped[list["MovieReleaseMedia"]] = relationship(
        back_populates="release",
        cascade="all, delete-orphan",
    )


class MovieReleaseMedia(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_release_media"
    __table_args__ = (
        UniqueConstraint("release_id", "media_number", name="unique_movie_release_media"),
        Index("idx_movie_release_media_release_id", "release_id"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movie_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_number: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))
    aspect_ratio: Mapped[str | None] = mapped_column(String(16))
    screen_ratio: Mapped[str | None] = mapped_column(String(50))
    color: Mapped[str | None] = mapped_column(String(64))
    num_discs: Mapped[int | None] = mapped_column(Integer)
    nr_layers: Mapped[int | None] = mapped_column(Integer)
    layers: Mapped[str | None] = mapped_column(String(50))
    audio_tracks: Mapped[str | None] = mapped_column(String(500))
    subtitles: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    release: Mapped[MovieRelease] = relationship(back_populates="media")


class MovieWorkContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_work_contributions"
    __table_args__ = (
        UniqueConstraint("work_id", "person_id", "role", name="unique_movie_work_contribution"),
        Index("idx_movie_work_contributions_work_id", "work_id"),
        Index("idx_movie_work_contributions_role", "work_id", "role"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movie_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    character_name: Mapped[str | None] = mapped_column(String(255))
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    work: Mapped[MovieWork] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class MovieWorkIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "movie_work_identifiers"
    __table_args__ = (
        UniqueConstraint("work_id", "identifier_type", "value", name="unique_movie_work_identifier"),
        Index("idx_movie_work_identifiers_work_id", "work_id"),
        Index("idx_movie_work_identifiers_type_value", "identifier_type", "value"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movie_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, server_default="{}")

    work: Mapped[MovieWork] = relationship(back_populates="identifiers")


class GameWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_works"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    original_language: Mapped[str | None] = mapped_column(String(16))
    age_rating: Mapped[str | None] = mapped_column(String(64))
    audience_rating: Mapped[str | None] = mapped_column(String(64))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    releases: Mapped[list["GameRelease"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    organization_links: Mapped[list["EntityOrganization"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityOrganization.entity_id) == GameWork.id,
            EntityOrganization.entity_type == "game_work",
        ),
        viewonly=True,
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == GameWork.id,
            ExternalProviderId.entity_type == "game_work",
        ),
        viewonly=True,
    )


class GameRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "game_releases"
    __table_args__ = (
        Index("ix_game_releases_work_platform", "work_id", "platform"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_title: Mapped[str | None] = mapped_column(String(255))
    platform: Mapped[str | None] = mapped_column(String(128), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    region_code: Mapped[str | None] = mapped_column(String(32), index=True)
    format: Mapped[str | None] = mapped_column(String(64), index=True)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[GameWork] = relationship(back_populates="releases")


class BoardGameWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_works"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    original_language: Mapped[str | None] = mapped_column(String(16))
    age_rating: Mapped[str | None] = mapped_column(String(64))
    audience_rating: Mapped[str | None] = mapped_column(String(64))
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    editions: Mapped[list["BoardGameEdition"]] = relationship(
        back_populates="work",
        cascade="all, delete-orphan",
    )
    person_links: Mapped[list["EntityPerson"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityPerson.entity_id) == BoardGameWork.id,
            EntityPerson.entity_type == "boardgame_work",
        ),
        viewonly=True,
    )
    organization_links: Mapped[list["EntityOrganization"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(EntityOrganization.entity_id) == BoardGameWork.id,
            EntityOrganization.entity_type == "boardgame_work",
        ),
        viewonly=True,
    )
    provider_links: Mapped[list["ExternalProviderId"]] = relationship(
        primaryjoin=lambda: and_(
            foreign(ExternalProviderId.entity_id) == BoardGameWork.id,
            ExternalProviderId.entity_type == "boardgame_work",
        ),
        viewonly=True,
    )


class BoardGameEdition(UuidMixin, TimestampMixin, Base):
    __tablename__ = "boardgame_editions"
    __table_args__ = (
        Index("ix_boardgame_editions_work_release", "work_id", "release_date"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boardgame_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edition_title: Mapped[str | None] = mapped_column(String(255))
    format: Mapped[str | None] = mapped_column(String(64))
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    catalog_number: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), index=True)
    release_status: Mapped[str | None] = mapped_column(String(64), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    language: Mapped[str | None] = mapped_column(String(16), index=True)
    country: Mapped[str | None] = mapped_column(String(32), index=True)
    age_rating: Mapped[str | None] = mapped_column(String(64), index=True)
    audience_rating: Mapped[str | None] = mapped_column(String(64))
    min_players: Mapped[int | None] = mapped_column(Integer)
    max_players: Mapped[int | None] = mapped_column(Integer)
    playing_time_minutes: Mapped[int | None] = mapped_column(Integer)
    min_age: Mapped[int | None] = mapped_column(Integer)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[BoardGameWork] = relationship(back_populates="editions")


# ========================
# Manga v1 Schema
# ========================


class MangaWork(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_works"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(16))
    original_publication_date: Mapped[date | None] = mapped_column(Date)
    first_publication_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    chapters: Mapped[list["MangaChapter"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )
    contributions: Mapped[list["MangaContribution"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )
    identifiers: Mapped[list["MangaIdentifier"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )
    character_appearances: Mapped[list["MangaCharacterAppearance"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )
    series_memberships: Mapped[list["MangaSeriesMembership"]] = relationship(
        back_populates="work", cascade="all, delete-orphan", lazy="selectin"
    )


class MangaChapter(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_chapters"

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_number: Mapped[float | None] = mapped_column(Float)
    chapter_title: Mapped[str | None] = mapped_column(String(255))
    publication_date: Mapped[date | None] = mapped_column(Date)
    page_count: Mapped[int | None]
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[MangaWork] = relationship(back_populates="chapters")


class MangaContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_contributions"
    __table_args__ = (
        CheckConstraint(
            "(work_id IS NOT NULL AND chapter_id IS NULL) OR (work_id IS NULL AND chapter_id IS NOT NULL)",
            name="ck_manga_contributions_xor_work_chapter",
        ),
    )

    work_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), index=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_chapters.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[MangaWork | None] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class MangaIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "work_id",
            "identifier_type",
            "normalized_value",
            name="uq_manga_identifiers_work_type_normalized",
        ),
        Index("ix_manga_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[MangaWork] = relationship(back_populates="identifiers")


class MangaCharacterAppearance(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_character_appearances"
    __table_args__ = (
        UniqueConstraint(
            "work_id",
            "character_id",
            "role",
            name="uq_manga_character_appearances_work_character_role",
        ),
        Index("ix_manga_character_appearances_work_role", "work_id", "role"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="featured", index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[MangaWork] = relationship(back_populates="character_appearances")
    character: Mapped["Character"] = relationship()


class MangaSeriesMembership(UuidMixin, TimestampMixin, Base):
    __tablename__ = "manga_series_memberships"
    __table_args__ = (
        UniqueConstraint("work_id", "series_id", name="uq_manga_series_memberships_work_series"),
        Index("ix_manga_series_memberships_series_sequence", "series_id", "sequence"),
    )

    work_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[float | None] = mapped_column(Float)
    display_number: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    work: Mapped[MangaWork] = relationship(back_populates="series_memberships")
    series: Mapped[Series] = relationship()


# ========================
# Anime v1 Schema
# ========================


class AnimeSeries(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_series"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    original_language: Mapped[str | None] = mapped_column(String(16))
    original_air_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    anime_type: Mapped[str | None] = mapped_column(String(64), index=True)
    episode_count: Mapped[int | None]
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    episodes: Mapped[list["AnimeEpisode"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )
    contributions: Mapped[list["AnimeContribution"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )
    identifiers: Mapped[list["AnimeIdentifier"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )
    character_appearances: Mapped[list["AnimeCharacterAppearance"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )


class AnimeEpisode(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_episodes"

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    episode_number: Mapped[int | None]
    episode_title: Mapped[str | None] = mapped_column(String(255))
    air_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(2048))
    cover_image_key: Mapped[str | None] = mapped_column(String(255))
    runtime_minutes: Mapped[int | None]
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[AnimeSeries] = relationship(back_populates="episodes")


class AnimeContribution(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_contributions"
    __table_args__ = (
        CheckConstraint(
            "(series_id IS NOT NULL AND episode_id IS NULL) OR (series_id IS NULL AND episode_id IS NOT NULL)",
            name="ck_anime_contributions_xor_series_episode",
        ),
    )

    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_series.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_episodes.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[AnimeSeries | None] = relationship(back_populates="contributions")
    person: Mapped["Person"] = relationship()


class AnimeIdentifier(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "identifier_type",
            "normalized_value",
            name="uq_anime_identifiers_series_type_normalized",
        ),
        Index("ix_anime_identifiers_type_value", "identifier_type", "normalized_value"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        index=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[AnimeSeries] = relationship(back_populates="identifiers")


class AnimeCharacterAppearance(UuidMixin, TimestampMixin, Base):
    __tablename__ = "anime_character_appearances"
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "character_id",
            "role",
            name="uq_anime_character_appearances_series_character_role",
        ),
        Index("ix_anime_character_appearances_series_role", "series_id", "role"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anime_series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="featured", index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[AnimeSeries] = relationship(back_populates="character_appearances")
    character: Mapped["Character"] = relationship()


# TV v1 Schema
# ========================




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
