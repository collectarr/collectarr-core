"""Single source of truth for canonical metadata fields.

Historically the catalog metadata fields were declared three times: as
``_KIND_ALLOWED_KEYS`` (which kind exposes which field), ``_NORMALIZED_VALUE_TYPES``
(the value type per field) and ``TYPED_KIND_METADATA_KEYS`` (which fields map to a
typed ``ItemKindMetadata*`` column). Adding a field meant editing every copy and
forgetting one silently broke ingest/correction (see the ``NormalizedItem.color``
regression).

This module declares each field once as a :class:`MetadataFieldSpec` and derives
those lookups from the registry. It is also the schema that the admin edit panel
and the Flutter app edit dialog should render from (see the unified-edit-fields
roadmap).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.base import ItemKind

# Value types understood by normalization/validation.
VALUE_TYPE_STRING = "string"
VALUE_TYPE_STRING_LIST = "string_list"
VALUE_TYPE_INTEGER = "integer"
VALUE_TYPE_TRACK_LIST = "track_list"

# Kinds that carry the physical video/disc spec fields.
VIDEO_KINDS: frozenset[ItemKind] = frozenset(
    {ItemKind.anime, ItemKind.bluray, ItemKind.movie, ItemKind.tv}
)
# Every active + legacy kind (genres applies to all of them).
ALL_KINDS: frozenset[ItemKind] = frozenset(ItemKind)


@dataclass(frozen=True)
class MetadataFieldSpec:
    """One editable canonical metadata field."""

    key: str
    value_type: str
    label: str
    #: ``True`` for fields shared by every kind (cover/format/audience metadata).
    common: bool = False
    #: ``True`` when the field maps to a typed ``ItemKindMetadata*`` column.
    typed: bool = False
    #: Kinds that expose a non-common field. Ignored for common fields.
    kinds: frozenset[ItemKind] = field(default_factory=frozenset)

    def applies_to(self, kind: ItemKind) -> bool:
        return self.common or kind in self.kinds


# --- Common fields (shared by every kind) -----------------------------------
_COMMON_FIELDS: tuple[MetadataFieldSpec, ...] = (
    MetadataFieldSpec("audience_rating", VALUE_TYPE_STRING, "Audience rating",
                      common=True, typed=True),
    MetadataFieldSpec("physical_format", VALUE_TYPE_STRING, "Physical format", common=True),
    MetadataFieldSpec("physical_format_label", VALUE_TYPE_STRING, "Physical format label",
                      common=True),
    MetadataFieldSpec("physical_format_media_family", VALUE_TYPE_STRING,
                      "Physical format media family", common=True),
    MetadataFieldSpec("physical_format_variant_type", VALUE_TYPE_STRING,
                      "Physical format variant type", common=True),
    MetadataFieldSpec("associated_image_id", VALUE_TYPE_STRING, "Associated image", common=True),
    MetadataFieldSpec("cover_delivery_url", VALUE_TYPE_STRING, "Cover delivery URL", common=True),
    MetadataFieldSpec("cover_policy", VALUE_TYPE_STRING, "Cover policy", common=True),
    MetadataFieldSpec("cover_source_url", VALUE_TYPE_STRING, "Cover source URL", common=True),
    MetadataFieldSpec("cover_status", VALUE_TYPE_STRING, "Cover status", common=True),
    MetadataFieldSpec("cover_storage", VALUE_TYPE_STRING, "Cover storage", common=True),
)

# --- Kind-scoped, typed fields ----------------------------------------------
_KIND_FIELDS: tuple[MetadataFieldSpec, ...] = (
    MetadataFieldSpec("genres", VALUE_TYPE_STRING_LIST, "Genres", typed=True, kinds=ALL_KINDS),
    MetadataFieldSpec("platforms", VALUE_TYPE_STRING_LIST, "Platforms", typed=True,
                      kinds=frozenset({ItemKind.game, ItemKind.boardgame})),
    MetadataFieldSpec("track_count", VALUE_TYPE_INTEGER, "Track count", typed=True,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("tracks", VALUE_TYPE_TRACK_LIST, "Tracks", typed=True,
                      kinds=frozenset({ItemKind.music})),
    MetadataFieldSpec("color", VALUE_TYPE_STRING, "Color", typed=True, kinds=VIDEO_KINDS),
    MetadataFieldSpec("nr_discs", VALUE_TYPE_INTEGER, "Number of discs", typed=True,
                      kinds=VIDEO_KINDS),
    MetadataFieldSpec("screen_ratio", VALUE_TYPE_STRING, "Screen ratio", typed=True,
                      kinds=VIDEO_KINDS),
    MetadataFieldSpec("audio_tracks", VALUE_TYPE_STRING, "Audio tracks", typed=True,
                      kinds=VIDEO_KINDS),
    MetadataFieldSpec("subtitles", VALUE_TYPE_STRING, "Subtitles", typed=True, kinds=VIDEO_KINDS),
    MetadataFieldSpec("layers", VALUE_TYPE_STRING, "Layers", typed=True, kinds=VIDEO_KINDS),
)

#: The canonical registry, ordered (common first, then kind-scoped).
METADATA_FIELDS: tuple[MetadataFieldSpec, ...] = _COMMON_FIELDS + _KIND_FIELDS

_FIELD_BY_KEY: dict[str, MetadataFieldSpec] = {spec.key: spec for spec in METADATA_FIELDS}


def field_spec(key: str) -> MetadataFieldSpec | None:
    return _FIELD_BY_KEY.get(key)


def common_field_keys() -> set[str]:
    return {spec.key for spec in METADATA_FIELDS if spec.common}


def kind_allowed_keys() -> dict[ItemKind, set[str]]:
    """Per-kind set of non-common field keys (mirrors the legacy lookup)."""
    result: dict[ItemKind, set[str]] = {kind: set() for kind in ItemKind}
    for spec in METADATA_FIELDS:
        if spec.common:
            continue
        for kind in spec.kinds:
            result[kind].add(spec.key)
    return result


def value_types() -> dict[str, str]:
    return {spec.key: spec.value_type for spec in METADATA_FIELDS}


def typed_field_keys() -> set[str]:
    return {spec.key for spec in METADATA_FIELDS if spec.typed}


def fields_for_kind(kind: ItemKind) -> list[MetadataFieldSpec]:
    """Ordered specs editable for a given kind (common + that kind's fields)."""
    return [spec for spec in METADATA_FIELDS if spec.applies_to(kind)]
