from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Generic, Protocol, TypeVar

from app.models.base import ItemKind


@dataclass(frozen=True)
class ProviderCapabilities:
    kind: ItemKind
    display_name: str
    kinds: tuple[ItemKind, ...] = ()
    supports_search: bool = True
    supports_ingest: bool = True
    requires_user_key: bool = False
    non_commercial_only: bool = False
    allows_redistribution: bool = False
    allows_image_mirroring: bool = False
    requires_attribution: bool = False
    license_name: str | None = None
    terms_url: str | None = None
    attribution_url: str | None = None
    rate_limit: str | None = None
    cache_policy: str | None = None

    @property
    def supported_kinds(self) -> tuple[ItemKind, ...]:
        return self.kinds or (self.kind,)

    def supports_kind(self, kind: ItemKind) -> bool:
        return kind in self.supported_kinds


@dataclass(frozen=True)
class ProviderSearchResult:
    provider: str
    provider_item_id: str
    title: str
    kind: ItemKind
    summary: str | None = None
    image_url: str | None = None
    candidate_type: str | None = None
    series_title: str | None = None
    issue_number: str | None = None
    volume_start_year: int | None = None
    variant_name: str | None = None
    is_variant: bool | None = None
    issue_count: int | None = None
    publisher: str | None = None
    character_preview: list[str] = field(default_factory=list)
    story_arc_preview: list[str] = field(default_factory=list)


ProviderRawT = TypeVar("ProviderRawT", covariant=True)


@dataclass(frozen=True)
class ProviderItem(Generic[ProviderRawT]):
    provider: str
    provider_item_id: str
    raw: ProviderRawT


@dataclass(frozen=True)
class NormalizedCredit:
    name: str
    role: str | None = None
    api_detail_url: str | None = None
    site_detail_url: str | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class NormalizedVariantCover:
    name: str
    cover_image_url: str
    thumbnail_image_url: str | None = None
    provider_item_id: str | None = None
    source_id: str | None = None
    caption: str | None = None


@dataclass(frozen=True)
class NormalizedRelation:
    relation_type: str
    title: str
    provider: str | None = None
    provider_id: str | None = None
    kind: ItemKind | None = None
    start_year: int | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class NormalizedTrack:
    position: int
    title: str
    duration_seconds: int | None = None
    artist: str | None = None
    disc_number: int | None = None


@dataclass(frozen=True)
class NormalizedEpisode:
    episode_number: int
    title: str
    provider_item_id: str | None = None
    overview: str | None = None
    air_date: date | None = None
    runtime_minutes: int | None = None
    page_count: int | None = None
    still_url: str | None = None


@dataclass(frozen=True)
class NormalizedSeason:
    season_number: int
    title: str
    provider_item_id: str | None = None
    overview: str | None = None
    air_date: date | None = None
    episode_count: int | None = None
    poster_url: str | None = None
    episodes: list[NormalizedEpisode] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedBundleMember:
    item: "NormalizedItem"
    role: str = "primary"
    sequence_number: int | None = None
    disc_number: int | None = None
    disc_label: str | None = None
    quantity: int = 1
    is_primary: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedBundleRelease:
    title: str
    bundle_type: str | None = None
    format: str | None = None
    variant_type: str | None = None
    packaging_type: str | None = None
    region: str | None = None
    language: str | None = None
    publisher: str | None = None
    sku: str | None = None
    barcode: str | None = None
    release_date: date | None = None
    cover_image_url: str | None = None
    provider_ids: dict[str, str] = field(default_factory=dict)
    members: list[NormalizedBundleMember] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedItem:
    kind: ItemKind
    title: str
    item_number: str | None = None
    synopsis: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    volume_number: float | None = None
    volume_start_year: int | None = None
    runtime_minutes: int | None = None
    page_count: int | None = None
    edition_title: str | None = None
    edition_format: str | None = None
    physical_format: str | None = None
    publisher: str | None = None
    imprint: str | None = None
    release_date: date | None = None
    isbn: str | None = None
    barcode: str | None = None
    cover_price_cents: int | None = None
    currency: str | None = None
    variant_name: str | None = None
    variant_type: str | None = None
    cover_image_url: str | None = None
    creators: list[NormalizedCredit] = field(default_factory=list)
    characters: list[NormalizedCredit] = field(default_factory=list)
    story_arcs: list[NormalizedCredit] = field(default_factory=list)
    provider_ids: dict[str, str] = field(default_factory=dict)
    volume_provider_ids: dict[str, str] = field(default_factory=dict)
    variant_covers: list[NormalizedVariantCover] = field(default_factory=list)
    relations: list[NormalizedRelation] = field(default_factory=list)
    tracks: list[NormalizedTrack] = field(default_factory=list)
    track_count: int | None = None
    catalog_number: str | None = None
    country: str | None = None
    release_status: str | None = None
    platforms: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    language: str | None = None
    age_rating: str | None = None
    audience_rating: str | None = None
    color: str | None = None
    nr_discs: int | None = None
    screen_ratio: str | None = None
    audio_tracks: str | None = None
    subtitles: str | None = None
    layers: str | None = None
    subtitle: str | None = None
    series_group: str | None = None
    bundle_release: NormalizedBundleRelease | None = None

    def __post_init__(self) -> None:
        if self.story_arcs or not self.genres or self.kind != ItemKind.comic:
            return
        object.__setattr__(
            self,
            "story_arcs",
            [NormalizedCredit(name=genre) for genre in self.genres if genre],
        )


class MetadataProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    @property
    def is_configured(self) -> bool: ...

    @property
    def status_message(self) -> str: ...

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]: ...

    async def get_item(self, provider_item_id: str) -> ProviderItem: ...

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem: ...
