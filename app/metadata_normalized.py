from collections.abc import Mapping
from typing import Any

from app.catalog.metadata_fields import (
    common_field_keys,
    kind_allowed_keys,
    typed_field_keys,
    value_types,
)
from app.models.base import ItemKind

NORMALIZED_SCHEMA_VERSION = 1

# Derived from the single field registry in app.catalog.metadata_fields so the
# allowed keys, value types and typed-column keys can never drift apart.
_COMMON_ALLOWED_KEYS = common_field_keys()

_KIND_ALLOWED_KEYS: dict[ItemKind, set[str]] = kind_allowed_keys()

_NORMALIZED_VALUE_TYPES: dict[str, str] = value_types()

TYPED_KIND_METADATA_KEYS = typed_field_keys()

ALLOWED_NORMALIZED_METADATA_KEYS = _COMMON_ALLOWED_KEYS | {
    key for keys in _KIND_ALLOWED_KEYS.values() for key in keys
}


def _allowed_keys_for_kind(kind: ItemKind | None) -> set[str]:
    if kind is None:
        return set(ALLOWED_NORMALIZED_METADATA_KEYS)
    return _COMMON_ALLOWED_KEYS | _KIND_ALLOWED_KEYS.get(kind, set())


def _is_valid_normalized_value(key: str, value: Any) -> bool:
    if key == "schema_version":
        return isinstance(value, int) and value > 0
    value_type = _NORMALIZED_VALUE_TYPES.get(key)
    if value_type == "string":
        return isinstance(value, str) and bool(value.strip())
    if value_type == "string_list":
        return isinstance(value, list) and all(isinstance(entry, str) for entry in value)
    if value_type == "integer":
        return isinstance(value, int) and value >= 0
    return True


def normalized_metadata_manifest() -> dict[str, Any]:
    common_fields = sorted(_COMMON_ALLOWED_KEYS)
    kind_fields = {
        kind.value: sorted(keys)
        for kind, keys in _KIND_ALLOWED_KEYS.items()
    }
    value_types = {
        key: _NORMALIZED_VALUE_TYPES[key]
        for key in sorted(ALLOWED_NORMALIZED_METADATA_KEYS)
        if key in _NORMALIZED_VALUE_TYPES
    }
    return {
        "schema_version": NORMALIZED_SCHEMA_VERSION,
        "common_fields": common_fields,
        "kind_fields": kind_fields,
        "value_types": value_types,
    }


def typed_metadata_payload(
    values: Mapping[str, Any] | None,
    *,
    kind: ItemKind | None,
) -> dict[str, Any]:
    cleaned = clean_normalized_metadata(values, kind=kind)
    cleaned.pop("schema_version", None)
    return {key: cleaned.get(key) for key in TYPED_KIND_METADATA_KEYS if key in cleaned}


def normalized_metadata_issues(
    values: Mapping[str, Any] | None,
    *,
    kind: ItemKind,
) -> list[str]:
    if not isinstance(values, Mapping):
        return ["normalized_not_object"]
    issues: list[str] = []
    allowed_keys = _allowed_keys_for_kind(kind)
    schema_version = values.get("schema_version")
    if not isinstance(schema_version, int):
        issues.append("schema_version_missing")
    elif schema_version != NORMALIZED_SCHEMA_VERSION:
        issues.append("schema_version_mismatch")
    for raw_key, raw_value in values.items():
        key = str(raw_key)
        if key == "schema_version":
            continue
        if key not in allowed_keys:
            issues.append(f"unknown_key:{key}")
            continue
        if not _is_valid_normalized_value(key, raw_value):
            issues.append(f"invalid_type:{key}")
    return sorted(set(issues))


def clean_normalized_metadata(
    values: Mapping[str, Any] | None,
    *,
    kind: ItemKind | None = None,
) -> dict[str, Any]:
    if not isinstance(values, Mapping):
        return {}
    allowed_keys = _allowed_keys_for_kind(kind)
    cleaned = {
        str(key): value
        for key, value in values.items()
        if str(key) in allowed_keys
        and value is not None
        and value != []
        and value != {}
        and _is_valid_normalized_value(str(key), value)
    }
    cleaned["schema_version"] = NORMALIZED_SCHEMA_VERSION
    return cleaned


def set_normalized_metadata(
    metadata_json: Mapping[str, Any] | None,
    normalized_values: Mapping[str, Any] | None,
    *,
    kind: ItemKind | None = None,
) -> dict[str, Any]:
    metadata = dict(metadata_json or {})
    normalized = clean_normalized_metadata(normalized_values, kind=kind)
    if normalized:
        metadata["normalized"] = normalized
    else:
        metadata.pop("normalized", None)
    return metadata


def merge_normalized_metadata(
    metadata_json: Mapping[str, Any] | None,
    updates: Mapping[str, Any] | None,
    *,
    kind: ItemKind | None = None,
) -> dict[str, Any]:
    metadata = dict(metadata_json or {})
    current = metadata.get("normalized")
    merged = dict(current) if isinstance(current, dict) else {}
    merged.pop("schema_version", None)
    if isinstance(updates, Mapping):
        merged.update(dict(updates))
    return set_normalized_metadata(metadata, merged, kind=kind)