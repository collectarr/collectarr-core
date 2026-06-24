import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.models.base import Base, ExternalProvider, ItemKind, SeriesRelationType, TimestampMixin, UuidMixin


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
    provider_links: Mapped[list["SeriesProviderLink"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )


class Volume(UuidMixin, TimestampMixin, Base):
    __tablename__ = "volumes"

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    volume_number: Mapped[float | None] = mapped_column(Float)
    start_year: Mapped[int | None]
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    series: Mapped[Series] = relationship(back_populates="volumes")
    items: Mapped[list["Item"]] = relationship(back_populates="volume")
    provider_links: Mapped[list["VolumeProviderLink"]] = relationship(
        back_populates="volume", cascade="all, delete-orphan"
    )


class Item(UuidMixin, TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (Index("ix_items_kind_title", "kind", "title"),)

    volume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("volumes.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title_extension: Mapped[str | None] = mapped_column(String(255))
    item_number: Mapped[str | None] = mapped_column(String(64), index=True)
    sort_key: Mapped[str | None] = mapped_column(String(255), index=True)
    synopsis: Mapped[str | None] = mapped_column(Text)
    release_type: Mapped[str | None] = mapped_column(String(64), index=True)
    season_number: Mapped[int | None] = mapped_column(Integer, index=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, index=True)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    volume: Mapped[Volume | None] = relationship(back_populates="items")
    editions: Mapped[list["Edition"]] = relationship(back_populates="item")
    primary_bundle_releases: Mapped[list["BundleRelease"]] = relationship(
        back_populates="primary_item",
        foreign_keys="BundleRelease.primary_item_id",
    )
    provider_links: Mapped[list["ItemProviderLink"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
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


class Edition(UuidMixin, TimestampMixin, Base):
    __tablename__ = "editions"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str | None] = mapped_column(String(100))
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
    release_date: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    item: Mapped[Item] = relationship(back_populates="editions")
    variants: Mapped[list["Variant"]] = relationship(back_populates="edition")


class ItemKindMetadata(UuidMixin, TimestampMixin, Base):
    __tablename__ = "item_kind_metadata"
    __table_args__ = (
        UniqueConstraint("item_id", name="uq_item_kind_metadata_item_id"),
        Index("ix_item_kind_metadata_kind", "kind"),
    )
    __mapper_args__ = {"polymorphic_on": "kind"}

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind, name="item_kind"), nullable=False)
    audience_rating: Mapped[str | None] = mapped_column(String(64), index=True)

    item: Mapped[Item] = relationship(back_populates="kind_metadata")


class ItemKindMetadataAnime(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_anime"
    __table_args__ = (CheckConstraint("nr_discs IS NULL OR nr_discs >= 0", name="ck_item_kind_metadata_anime_nr_discs_nonnegative"),)
    __mapper_args__ = {"polymorphic_identity": ItemKind.anime}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    color: Mapped[str | None] = mapped_column(String(64))
    nr_discs: Mapped[int | None] = mapped_column(Integer)
    screen_ratio: Mapped[str | None] = mapped_column(String(64))
    audio_tracks: Mapped[str | None] = mapped_column(String(255))
    subtitles: Mapped[str | None] = mapped_column(String(255))
    layers: Mapped[str | None] = mapped_column(String(255))


class ItemKindMetadataBoardGame(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_boardgame"
    __mapper_args__ = {"polymorphic_identity": ItemKind.boardgame}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    platforms: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class ItemKindMetadataBook(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_book"
    __mapper_args__ = {"polymorphic_identity": ItemKind.book}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class ItemKindMetadataBluray(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_bluray"
    __table_args__ = (CheckConstraint("nr_discs IS NULL OR nr_discs >= 0", name="ck_item_kind_metadata_bluray_nr_discs_nonnegative"),)
    __mapper_args__ = {"polymorphic_identity": ItemKind.bluray}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    color: Mapped[str | None] = mapped_column(String(64))
    nr_discs: Mapped[int | None] = mapped_column(Integer)
    screen_ratio: Mapped[str | None] = mapped_column(String(64))
    audio_tracks: Mapped[str | None] = mapped_column(String(255))
    subtitles: Mapped[str | None] = mapped_column(String(255))
    layers: Mapped[str | None] = mapped_column(String(255))


class ItemKindMetadataCollection(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_collection"
    __mapper_args__ = {"polymorphic_identity": ItemKind.collection}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class ItemKindMetadataComic(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_comic"
    __mapper_args__ = {"polymorphic_identity": ItemKind.comic}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class ItemKindMetadataGame(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_game"
    __mapper_args__ = {"polymorphic_identity": ItemKind.game}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    platforms: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class ItemKindMetadataManga(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_manga"
    __mapper_args__ = {"polymorphic_identity": ItemKind.manga}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class ItemKindMetadataMovie(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_movie"
    __table_args__ = (CheckConstraint("nr_discs IS NULL OR nr_discs >= 0", name="ck_item_kind_metadata_movie_nr_discs_nonnegative"),)
    __mapper_args__ = {"polymorphic_identity": ItemKind.movie}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    color: Mapped[str | None] = mapped_column(String(64))
    nr_discs: Mapped[int | None] = mapped_column(Integer)
    screen_ratio: Mapped[str | None] = mapped_column(String(64))
    audio_tracks: Mapped[str | None] = mapped_column(String(255))
    subtitles: Mapped[str | None] = mapped_column(String(255))
    layers: Mapped[str | None] = mapped_column(String(255))


class ItemKindMetadataMusic(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_music"
    __table_args__ = (CheckConstraint("track_count IS NULL OR track_count >= 0", name="ck_item_kind_metadata_music_track_count_nonnegative"),)
    __mapper_args__ = {"polymorphic_identity": ItemKind.music}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    track_count: Mapped[int | None] = mapped_column(Integer)
    tracks: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)


class ItemKindMetadataTv(ItemKindMetadata):
    __tablename__ = "item_kind_metadata_tv"
    __table_args__ = (CheckConstraint("nr_discs IS NULL OR nr_discs >= 0", name="ck_item_kind_metadata_tv_nr_discs_nonnegative"),)
    __mapper_args__ = {"polymorphic_identity": ItemKind.tv}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_kind_metadata.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    color: Mapped[str | None] = mapped_column(String(64))
    nr_discs: Mapped[int | None] = mapped_column(Integer)
    screen_ratio: Mapped[str | None] = mapped_column(String(64))
    audio_tracks: Mapped[str | None] = mapped_column(String(255))
    subtitles: Mapped[str | None] = mapped_column(String(255))
    layers: Mapped[str | None] = mapped_column(String(255))


class Variant(UuidMixin, TimestampMixin, Base):
    __tablename__ = "variants"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("editions.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_type: Mapped[str | None] = mapped_column(String(64), index=True)
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
    provider_links: Mapped[list["BundleReleaseProviderLink"]] = relationship(
        back_populates="bundle_release", cascade="all, delete-orphan"
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


class ItemProviderLink(UuidMixin, TimestampMixin, Base):
    __tablename__ = "item_provider_links"
    __table_args__ = (
        UniqueConstraint("item_id", "provider", name="uq_item_provider_links_owner_provider"),
        UniqueConstraint("provider", "provider_item_id", name="uq_item_provider_links_provider_item"),
        Index("ix_item_provider_links_item", "item_id"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False, index=True
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    site_url: Mapped[str | None] = mapped_column(String(1024))
    api_url: Mapped[str | None] = mapped_column(String(1024))

    item: Mapped[Item] = relationship(back_populates="provider_links")

    @property
    def entity_type(self) -> str:
        return "item"


class SeriesProviderLink(UuidMixin, TimestampMixin, Base):
    __tablename__ = "series_provider_links"
    __table_args__ = (
        UniqueConstraint("series_id", "provider", name="uq_series_provider_links_owner_provider"),
        UniqueConstraint("provider", "provider_item_id", name="uq_series_provider_links_provider_item"),
        Index("ix_series_provider_links_series", "series_id"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False, index=True
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    site_url: Mapped[str | None] = mapped_column(String(1024))
    api_url: Mapped[str | None] = mapped_column(String(1024))

    series: Mapped[Series] = relationship(back_populates="provider_links")

    @property
    def entity_type(self) -> str:
        return "series"


class VolumeProviderLink(UuidMixin, TimestampMixin, Base):
    __tablename__ = "volume_provider_links"
    __table_args__ = (
        UniqueConstraint("volume_id", "provider", name="uq_volume_provider_links_owner_provider"),
        UniqueConstraint("provider", "provider_item_id", name="uq_volume_provider_links_provider_item"),
        Index("ix_volume_provider_links_volume", "volume_id"),
    )

    volume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("volumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False, index=True
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    site_url: Mapped[str | None] = mapped_column(String(1024))
    api_url: Mapped[str | None] = mapped_column(String(1024))

    volume: Mapped[Volume] = relationship(back_populates="provider_links")

    @property
    def entity_type(self) -> str:
        return "volume"


class BundleReleaseProviderLink(UuidMixin, TimestampMixin, Base):
    __tablename__ = "bundle_release_provider_links"
    __table_args__ = (
        UniqueConstraint(
            "bundle_release_id",
            "provider",
            name="uq_bundle_release_provider_links_owner_provider",
        ),
        UniqueConstraint(
            "provider",
            "provider_item_id",
            name="uq_bundle_release_provider_links_provider_item",
        ),
        Index("ix_bundle_release_provider_links_bundle_release", "bundle_release_id"),
    )

    bundle_release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bundle_releases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False, index=True
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    site_url: Mapped[str | None] = mapped_column(String(1024))
    api_url: Mapped[str | None] = mapped_column(String(1024))

    bundle_release: Mapped[BundleRelease] = relationship(back_populates="provider_links")

    @property
    def entity_type(self) -> str:
        return "bundle_release"


class ExternalProviderId(UuidMixin, TimestampMixin, Base):
    __tablename__ = "external_provider_ids"
    __table_args__ = (
        UniqueConstraint("provider", "provider_item_id", name="uq_provider_provider_item_id"),
        Index("ix_external_entity", "entity_type", "entity_id"),
    )

    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_url: Mapped[str | None] = mapped_column(String(1024))
    api_url: Mapped[str | None] = mapped_column(String(1024))


class Organization(UuidMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(64), index=True)
    country: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Person(UuidMixin, TimestampMixin, Base):
    __tablename__ = "persons"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class EntityOrganization(UuidMixin, TimestampMixin, Base):
    __tablename__ = "entity_organizations"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "organization_id",
            "role",
            name="uq_entity_organization_role",
        ),
        Index("ix_entity_organizations_entity", "entity_type", "entity_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    organization: Mapped[Organization] = relationship()


class EntityPerson(UuidMixin, TimestampMixin, Base):
    __tablename__ = "entity_persons"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "person_id",
            "role",
            name="uq_entity_person_role",
        ),
        Index("ix_entity_persons_entity", "entity_type", "entity_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    person: Mapped[Person] = relationship()


class StoryArc(UuidMixin, TimestampMixin, Base):
    __tablename__ = "story_arcs"
    __table_args__ = (
        UniqueConstraint("name", "publisher", name="uq_story_arcs_name_publisher"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(255), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class StoryArcItem(UuidMixin, TimestampMixin, Base):
    __tablename__ = "story_arc_items"
    __table_args__ = (
        UniqueConstraint("story_arc_id", "item_id", name="uq_story_arc_item"),
        Index("ix_story_arc_items_story_arc", "story_arc_id"),
        Index("ix_story_arc_items_item", "item_id"),
    )

    story_arc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_arcs.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int | None] = mapped_column(Integer)

    story_arc: Mapped[StoryArc] = relationship()
    item: Mapped[Item] = relationship(back_populates="story_arc_items")


class Character(UuidMixin, TimestampMixin, Base):
    __tablename__ = "characters"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    canonical_name: Mapped[str | None] = mapped_column(String(255), index=True)
    aliases: Mapped[list[str] | None] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    first_appearance_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="SET NULL"), index=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class CharacterAppearance(UuidMixin, TimestampMixin, Base):
    __tablename__ = "character_appearances"
    __table_args__ = (
        UniqueConstraint("character_id", "item_id", name="uq_character_appearance"),
        Index("ix_character_appearances_character", "character_id"),
        Index("ix_character_appearances_item", "item_id"),
    )

    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    character: Mapped[Character] = relationship()
    item: Mapped[Item] = relationship(back_populates="character_appearances")


class Tag(UuidMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("kind", "name", name="uq_tags_kind_name"),)

    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class EntityTag(UuidMixin, TimestampMixin, Base):
    __tablename__ = "entity_tags"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "tag_id", name="uq_entity_tag"),
        Index("ix_entity_tags_entity", "entity_type", "entity_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    tag: Mapped[Tag] = relationship()


class ImageAsset(UuidMixin, TimestampMixin, Base):
    __tablename__ = "image_assets"
    __table_args__ = (Index("ix_image_assets_entity", "entity_type", "entity_id"),)

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    image_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(512))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    provider: Mapped[str | None] = mapped_column(String(64), index=True)
    attribution: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    phash: Mapped[str | None] = mapped_column(String(128), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ImageCacheEntry(UuidMixin, TimestampMixin, Base):
    __tablename__ = "image_cache_entries"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_image_cache_object_key"),
        Index("ix_image_cache_provider_source", "provider", "source_url"),
        Index("ix_image_cache_last_accessed", "last_accessed_at"),
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_item_id: Mapped[str | None] = mapped_column(String(255), index=True)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    public_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderIngestJob(UuidMixin, TimestampMixin, Base):
    __tablename__ = "provider_ingest_jobs"
    __table_args__ = (
        Index("ix_provider_ingest_jobs_status_next_run", "status", "next_run_at"),
        Index("ix_provider_ingest_jobs_provider_item", "provider", "provider_item_id"),
    )

    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False, index=True
    )
    provider_item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)


class AdminAuditLog(UuidMixin, TimestampMixin, Base):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("ix_admin_audit_logs_action_created", "action", "created_at"),
        Index("ix_admin_audit_logs_entity", "entity_type", "entity_id"),
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class MetadataProposal(UuidMixin, TimestampMixin, Base):
    __tablename__ = "metadata_proposals"
    __table_args__ = (Index("ix_metadata_proposals_status_provider", "status", "provider"),)

    provider: Mapped[ExternalProvider] = mapped_column(
        Enum(ExternalProvider, name="external_provider"), nullable=False, index=True
    )
    provider_item_id: Mapped[str | None] = mapped_column(String(255), index=True)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)


class AdminReleaseMediaMappingRule(UuidMixin, TimestampMixin, Base):
    __tablename__ = "admin_release_media_mapping_rules"
    __table_args__ = (
        Index(
            "ix_admin_release_media_mapping_rules_lookup",
            "release_type",
            "provider",
            "is_active",
            "priority",
        ),
    )

    provider: Mapped[ExternalProvider | None] = mapped_column(
        Enum(ExternalProvider, name="external_provider", create_type=False),
        nullable=True,
        index=True,
    )
    release_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_kind: Mapped[ItemKind] = mapped_column(
        Enum(ItemKind, name="item_kind", create_type=False), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class SeriesRelation(UuidMixin, TimestampMixin, Base):
    __tablename__ = "series_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_series_id",
            "target_series_id",
            "relation_type",
            name="uq_series_relations_source_target_type",
        ),
    )

    source_series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    target_series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[SeriesRelationType] = mapped_column(
        Enum(SeriesRelationType, name="series_relation_type", create_type=False),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    source_series: Mapped[Series] = relationship(
        foreign_keys=[source_series_id],
    )
    target_series: Mapped[Series] = relationship(
        foreign_keys=[target_series_id],
    )
