"""Single source of truth for canonical metadata fields.

Each kind declares edit fields with :class:`MetadataFieldSpec`. Normalized
storage rules live in a separate registry below; root table, entity type, and
canonical write ownership are resolved once from the Catalog Kind registry.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from app.catalog.common_metadata_fields import (
    _EDITABLE_COMMON_FIELDS,
    _EDITORIAL_FIELDS,
    _INTERNAL_COMMON_FIELDS,
)
from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS, catalog_kind_for
from app.catalog.metadata_field_spec import (
    CATALOG_KINDS,
    INPUT_LIST,
    SECTION_RELATIONS,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
    NormalizedFieldSpec,
)
from app.models.base import ItemKind

_INTERNAL_DERIVED_KEYS = {
    "format_templateimage",
    "format_scaledimage",
    "country_scaledimage",
    "language_scaledimage",
    "audiencerating_templateimage",
    "region_scaledimage",
    "audio_templateimage",
    "physical_format_label",
    "physical_format_media_family",
    "physical_format_variant_type",
    "associated_image_id",
    "cover_delivery_url",
    "cover_policy",
    "cover_source_url",
    "cover_status",
    "cover_storage",
}

METADATA_FIELD_SCHEMA_VERSION = 2


def contract_rows(kinds: Iterable[ItemKind] | None = None) -> list[dict[str, object]]:
    active_kinds = (
        tuple(kinds)
        if kinds is not None
        else tuple(definition.kind for definition in CATALOG_KIND_DEFINITIONS)
    )
    rows: list[dict[str, object]] = []
    for spec in METADATA_FIELDS:
        if spec.correction_only:
            continue
        applicable_kinds = tuple(kind for kind in active_kinds if spec.applies_to(kind))
        if not applicable_kinds:
            continue
        for kind in applicable_kinds:
            rows.append(
                {
                    "key": spec.key,
                    "kind": kind.value,
                    "label": spec.label,
                    "valueType": spec.value_type,
                    "section": spec.section,
                    "input": spec.input,
                    "editable": spec.editable,
                }
            )
    return rows


# --- Kind-owned field composition --------------------------------------------
def _coalesce_identical_specs(
    specs: Iterable[MetadataFieldSpec],
) -> tuple[MetadataFieldSpec, ...]:
    """Compose matching kind declarations without duplicating the API field."""
    ordered: dict[tuple[object, ...], MetadataFieldSpec] = {}
    for spec in specs:
        identity = (
            spec.key,
            spec.value_type,
            spec.label,
            spec.editable,
            spec.section,
            spec.input,
            spec.correction_only,
        )
        existing = ordered.get(identity)
        if existing is None:
            ordered[identity] = spec
        else:
            ordered[identity] = replace(existing, kinds=existing.kinds | spec.kinds)
    return tuple(ordered.values())


_SHARED_KIND_FIELDS: tuple[MetadataFieldSpec, ...] = (
    MetadataFieldSpec(
        "genres",
        VALUE_TYPE_STRING_LIST,
        "Genres",
        kinds=CATALOG_KINDS,
        section=SECTION_RELATIONS,
        input=INPUT_LIST,
    ),
)

_KIND_FIELDS = _coalesce_identical_specs(
    spec for definition in CATALOG_KIND_DEFINITIONS for spec in definition.field_specs
)

# Shared declarations are followed by the fields composed directly from each
# kind definition, then by editorial-only fields.
METADATA_FIELDS: tuple[MetadataFieldSpec, ...] = (
    _INTERNAL_COMMON_FIELDS
    + _EDITABLE_COMMON_FIELDS
    + _SHARED_KIND_FIELDS
    + _KIND_FIELDS
    + _EDITORIAL_FIELDS
)

_FIELDS_BY_KEY: dict[str, tuple[MetadataFieldSpec, ...]] = {
    key: tuple(spec for spec in METADATA_FIELDS if spec.key == key)
    for key in {spec.key for spec in METADATA_FIELDS}
}

_NORMALIZED_FIELD_KEYS = {
    *(_INTERNAL_DERIVED_KEYS),
    "genres",
    "audience_rating",
    "color",
    "platforms",
}
NORMALIZED_FIELD_SPECS: tuple[NormalizedFieldSpec, ...] = tuple(
    NormalizedFieldSpec(
        key=key,
        kinds=(
            CATALOG_KINDS
            if key in _INTERNAL_DERIVED_KEYS or key == "genres"
            else next(spec.kinds for spec in _FIELDS_BY_KEY[key] if spec.kinds)
        ),
        typed=key not in _INTERNAL_DERIVED_KEYS,
        common=key in _INTERNAL_DERIVED_KEYS,
    )
    for key in sorted(_NORMALIZED_FIELD_KEYS)
)
_NORMALIZED_FIELDS_BY_KEY = {spec.key: spec for spec in NORMALIZED_FIELD_SPECS}


def normalized_field_spec(key: str) -> NormalizedFieldSpec | None:
    return _NORMALIZED_FIELDS_BY_KEY.get(key)


def field_spec(key: str, kind: ItemKind | None = None) -> MetadataFieldSpec | None:
    candidates = _FIELDS_BY_KEY.get(key, ())
    if kind is not None:
        return next((spec for spec in candidates if spec.applies_to(kind)), None)
    return candidates[0] if len(candidates) == 1 else None


def common_field_keys() -> set[str]:
    """Return normalized fields shared by every canonical kind."""
    return {spec.key for spec in NORMALIZED_FIELD_SPECS if spec.common}


def kind_allowed_keys() -> dict[ItemKind, set[str]]:
    """Per-kind set of non-common normalized field keys."""
    result: dict[ItemKind, set[str]] = {kind: set() for kind in CATALOG_KINDS}
    for spec in NORMALIZED_FIELD_SPECS:
        if spec.common:
            continue
        for kind in spec.kinds:
            result[kind].add(spec.key)
    return result


def value_types() -> dict[str, str]:
    """Normalized field value types (mirrors ``_NORMALIZED_VALUE_TYPES``)."""
    field_specs = {spec.key: spec for spec in METADATA_FIELDS}
    return {
        spec.key: field_specs[spec.key].value_type
        for spec in NORMALIZED_FIELD_SPECS
        if spec.key in field_specs
    }


def typed_field_keys() -> set[str]:
    """Normalized fields backed by a typed canonical kind table column."""
    return {spec.key for spec in NORMALIZED_FIELD_SPECS if spec.typed}


def fields_for_kind(
    kind: ItemKind,
    *,
    editable_only: bool = False,
    include_correction_only: bool = False,
) -> list[MetadataFieldSpec]:
    """Ordered specs for a kind (common + that kind's fields)."""
    return [
        spec
        for spec in METADATA_FIELDS
        if spec.applies_to(kind)
        and (not editable_only or spec.editable)
        and (include_correction_only or not spec.correction_only)
    ]


def editable_fields() -> list[MetadataFieldSpec]:
    """All user-editable specs, in registry order."""
    return [spec for spec in METADATA_FIELDS if spec.editable and not spec.correction_only]


def editable_field_keys() -> set[str]:
    """Editable canonical field keys accepted by proposal/correction payloads."""
    return {spec.key for spec in editable_fields()}


def canonical_correction_field_spec(kind: ItemKind, key: str) -> MetadataFieldSpec | None:
    """Return *key* when it is valid for a canonical correction target."""

    spec = field_spec(key, kind)
    if spec is None or not spec.editable:
        return None
    if key in _INTERNAL_DERIVED_KEYS:
        return None
    return spec


def canonical_correction_target(
    kind: ItemKind,
    keys: Iterable[str],
) -> tuple[str, str] | None:
    """Resolve one canonical scope/entity type for a proposal field set."""

    target: tuple[str, str] | None = None
    for key in keys:
        spec = canonical_correction_field_spec(kind, key)
        if spec is None:
            return None
        current = ("catalog_item", catalog_kind_for(kind).entity_type)
        if target is None:
            target = current
        elif target != current:
            return None
    return target


def canonical_entity_type_for_scope(kind: ItemKind, scope: str) -> str | None:
    """Return the canonical entity type for a structural correction scope."""

    if scope != "catalog_item":
        return None
    try:
        return catalog_kind_for(kind).entity_type
    except ValueError:
        return None
