from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Protocol

from app.models.base import ItemKind


@dataclass(frozen=True)
class ProviderCapabilities:
    kind: ItemKind
    display_name: str
    supports_search: bool = True
    supports_ingest: bool = True
    requires_user_key: bool = False
    non_commercial_only: bool = False
    allows_redistribution: bool = False
    requires_attribution: bool = False
    license_name: str | None = None
    terms_url: str | None = None
    attribution_url: str | None = None
    rate_limit: str | None = None
    cache_policy: str | None = None


@dataclass(frozen=True)
class ProviderSearchResult:
    provider: str
    provider_item_id: str
    title: str
    kind: ItemKind
    summary: str | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class ProviderItem:
    provider: str
    provider_item_id: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class NormalizedCredit:
    name: str
    role: str | None = None
    api_detail_url: str | None = None
    site_detail_url: str | None = None


@dataclass(frozen=True)
class NormalizedItem:
    kind: ItemKind
    title: str
    item_number: str | None = None
    synopsis: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    volume_number: int | None = None
    volume_start_year: int | None = None
    page_count: int | None = None
    edition_title: str | None = None
    edition_format: str | None = None
    publisher: str | None = None
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


class MetadataProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities

    @property
    def is_configured(self) -> bool: ...

    @property
    def status_message(self) -> str: ...

    async def search(self, query: str) -> list[ProviderSearchResult]: ...

    async def get_item(self, provider_item_id: str) -> ProviderItem: ...

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem: ...
