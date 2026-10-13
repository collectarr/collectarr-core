"""Public media navigation config derived from Catalog Kind definitions."""

from dataclasses import dataclass

from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS
from app.catalog.physical_formats import PhysicalFormatConfig
from app.models.base import ItemKind


@dataclass(frozen=True)
class MediaTypeConfig:
    kind: ItemKind
    singular_label: str
    plural_label: str
    route_segments: tuple[str, ...]
    item_number_sort_padding: int | None = None
    is_top_level: bool = True
    physical_formats: tuple[PhysicalFormatConfig, ...] = ()

    @property
    def primary_route_segment(self) -> str:
        return self.route_segments[0] if self.route_segments else ""


_CATALOG_MEDIA_TYPES = tuple(
    MediaTypeConfig(
        kind=definition.kind,
        singular_label=definition.singular_label,
        plural_label=definition.plural_label,
        route_segments=definition.route_segments,
        item_number_sort_padding=definition.item_number_sort_padding,
        physical_formats=definition.physical_formats,
    )
    for definition in CATALOG_KIND_DEFINITIONS
)

_COLLECTION_MEDIA_TYPE = MediaTypeConfig(
    kind=ItemKind.collection,
    singular_label="Collection",
    plural_label="Collections",
    route_segments=("collections", "collection"),
    is_top_level=False,
)

media_types: tuple[MediaTypeConfig, ...] = (
    *_CATALOG_MEDIA_TYPES,
    _COLLECTION_MEDIA_TYPE,
)

top_level_media_types: tuple[MediaTypeConfig, ...] = tuple(
    config for config in media_types if config.is_top_level
)

_MEDIA_TYPES_BY_KIND = {config.kind: config for config in media_types}
_MEDIA_TYPES_BY_ROUTE = {
    route_segment: config for config in media_types for route_segment in config.route_segments
}


def media_type_for_kind(kind: ItemKind) -> MediaTypeConfig | None:
    return _MEDIA_TYPES_BY_KIND.get(kind)


def media_type_for_route(route_segment: str) -> MediaTypeConfig | None:
    return _MEDIA_TYPES_BY_ROUTE.get(route_segment.strip().lower())
