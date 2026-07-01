from collections.abc import Mapping
from typing import Any

from app.catalog.metadata_fields import (
    common_field_keys,
    kind_allowed_keys,
    typed_field_keys,
    value_types,
)
from app.models import (
    Item,
    ItemKindMetadata,
    ItemKindMetadataAnime,
    ItemKindMetadataBoardGame,
    ItemKindMetadataBook,
    ItemKindMetadataCollection,
    ItemKindMetadataComic,
    ItemKindMetadataGame,
    ItemKindMetadataManga,
    ItemKindMetadataMovie,
    ItemKindMetadataMusic,
    ItemKindMetadataTaxonomy,
    ItemKindMetadataTv,
    MetadataTaxonomy,
)
from app.models.base import ItemKind

NORMALIZED_SCHEMA_VERSION = 1

# Derived from the single field registry in app.catalog.metadata_fields so the
# allowed keys, value types and typed-column keys can never drift apart.
_COMMON_ALLOWED_KEYS = common_field_keys()

_KIND_ALLOWED_KEYS: dict[ItemKind, set[str]] = kind_allowed_keys()

_NORMALIZED_VALUE_TYPES: dict[str, str] = value_types()

TYPED_KIND_METADATA_KEYS = typed_field_keys()

_KIND_METADATA_MODEL_BY_KIND: dict[ItemKind, type[ItemKindMetadata]] = {
    ItemKind.anime: ItemKindMetadataAnime,
    ItemKind.boardgame: ItemKindMetadataBoardGame,
    ItemKind.book: ItemKindMetadataBook,
    ItemKind.collection: ItemKindMetadataCollection,
    ItemKind.comic: ItemKindMetadataComic,
    ItemKind.game: ItemKindMetadataGame,
    ItemKind.manga: ItemKindMetadataManga,
    ItemKind.movie: ItemKindMetadataMovie,
    ItemKind.music: ItemKindMetadataMusic,
    ItemKind.tv: ItemKindMetadataTv,
}

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


def typed_kind_metadata_payload(
    values: Mapping[str, Any] | None,
    *,
    kind: ItemKind | None,
) -> dict[str, Any]:
    cleaned = clean_normalized_metadata(values, kind=kind)
    cleaned.pop("schema_version", None)
    return {key: cleaned.get(key) for key in TYPED_KIND_METADATA_KEYS if key in cleaned}


def item_kind_metadata_payload(value: ItemKindMetadata | None) -> dict[str, Any]:
    if value is None:
        return {}
    raw: dict[str, Any] = {}
    metadata_json = getattr(value, "metadata_json", None)
    metadata_json = metadata_json if isinstance(metadata_json, dict) else {}
    for key in TYPED_KIND_METADATA_KEYS:
        if key == "audience_rating":
            continue
        if key in {"genres", "platforms"}:
            raw[key] = getattr(value, key, None)
            continue
        if key in metadata_json:
            raw[key] = metadata_json.get(key)
        else:
            raw[key] = getattr(value, key, None)
    if getattr(value, "audience_rating", None) is not None:
        raw["audience_rating"] = value.audience_rating
    return {
        key: row
        for key, row in raw.items()
        if row is not None and row != [] and row != {}
    }


def typed_kind_metadata_for_item(item: object) -> dict[str, Any]:
    return item_kind_metadata_payload(getattr(item, "kind_metadata", None))


def upsert_item_kind_metadata(item: Item, normalized_values: Mapping[str, Any] | None) -> None:
    typed_payload = typed_kind_metadata_payload(normalized_values, kind=item.kind)
    genres_payload = typed_payload.pop("genres", None)
    platforms_payload = typed_payload.pop("platforms", None)
    has_typed_payload = any(
        value is not None for key, value in typed_payload.items() if key != "audience_rating"
    ) or typed_payload.get("audience_rating") is not None
    if not has_typed_payload and not genres_payload and not platforms_payload:
        item.kind_metadata = None
        return
    metadata = item.kind_metadata
    metadata_model = _KIND_METADATA_MODEL_BY_KIND[item.kind]
    if metadata is None or not isinstance(metadata, metadata_model):
        metadata = metadata_model(item=item, kind=item.kind)
        item.kind_metadata = metadata
    metadata.kind = item.kind
    metadata.metadata_json = {
        key: value
        for key, value in typed_payload.items()
        if key not in {"audience_rating"} and value is not None
    } or None
    if "audience_rating" in typed_payload:
        metadata.audience_rating = typed_payload.get("audience_rating")
    for key in TYPED_KIND_METADATA_KEYS:
        if key in {"audience_rating", "genres", "platforms"}:
            continue
        if hasattr(metadata, key):
            setattr(metadata, key, typed_payload.get(key))
    _set_taxonomy_values(metadata, "genre", genres_payload)
    _set_taxonomy_values(metadata, "platform", platforms_payload)


def _set_taxonomy_values(
    metadata: ItemKindMetadata,
    category: str,
    values: list[str] | None,
) -> None:
    raw_values = values if isinstance(values, list) else []
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        text = str(raw or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    existing = [
        row
        for row in list(getattr(metadata, "taxonomy_links", []) or [])
        if getattr(row, "category", None) != category
    ]
    new_links = [
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
    ]
    metadata.taxonomy_links = [*existing, *new_links]


def patch_item_kind_metadata(item: Item, typed_updates: Mapping[str, Any]) -> None:
    current = item_kind_metadata_payload(item.kind_metadata)
    current.update(dict(typed_updates))
    upsert_item_kind_metadata(item, current)


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