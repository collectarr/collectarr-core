from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from app.models.base import ItemKind


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
class NormalizedItem:
    kind: ItemKind
    title: str
    item_number: str | None = None
    synopsis: str | None = None
    edition_title: str | None = None
    provider_ids: dict[str, str] = field(default_factory=dict)


class MetadataProvider(Protocol):
    name: str

    async def search(self, query: str) -> list[ProviderSearchResult]:
        ...

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        ...

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        ...

