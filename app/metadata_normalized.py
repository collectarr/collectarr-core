from collections.abc import Mapping
from typing import Any

from app.models.base import ItemKind

NORMALIZED_SCHEMA_VERSION = 1

_COMMON_ALLOWED_KEYS = {
    "associated_image_id",
    "audience_rating",
    "cover_delivery_url",
    "cover_policy",
    "cover_source_url",
    "cover_status",
    "cover_storage",
    "physical_format",
    "physical_format_label",
    "physical_format_media_family",
    "physical_format_variant_type",
}

_KIND_ALLOWED_KEYS: dict[ItemKind, set[str]] = {
    ItemKind.anime: {"genres", "color", "nr_discs", "screen_ratio", "audio_tracks", "subtitles", "layers"},
    ItemKind.boardgame: {"genres", "platforms"},
    ItemKind.book: {"genres"},
    ItemKind.bluray: {"genres", "color", "nr_discs", "screen_ratio", "audio_tracks", "subtitles", "layers"},
    ItemKind.collection: {"genres"},
    ItemKind.comic: {"genres"},
    ItemKind.game: {"genres", "platforms"},
    ItemKind.manga: {"genres"},
    ItemKind.movie: {"genres", "color", "nr_discs", "screen_ratio", "audio_tracks", "subtitles", "layers"},
    ItemKind.music: {"genres", "track_count", "tracks"},
    ItemKind.tv: {"genres", "color", "nr_discs", "screen_ratio", "audio_tracks", "subtitles", "layers"},
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
    if key in {
        "associated_image_id",
        "audience_rating",
        "cover_delivery_url",
        "cover_policy",
        "cover_source_url",
        "cover_status",
        "cover_storage",
        "physical_format",
        "physical_format_label",
        "physical_format_media_family",
        "physical_format_variant_type",
    }:
        return isinstance(value, str) and bool(value.strip())
    if key in {"genres", "platforms"}:
        return isinstance(value, list) and all(isinstance(entry, str) for entry in value)
    if key in {"color", "screen_ratio", "audio_tracks", "subtitles", "layers"}:
        return isinstance(value, str) and bool(value.strip())
    if key == "nr_discs":
        return isinstance(value, int) and value >= 0
    if key == "track_count":
        return isinstance(value, int) and value >= 0
    if key == "tracks":
        if not isinstance(value, list):
            return False
        for entry in value:
            if not isinstance(entry, Mapping):
                return False
            title = entry.get("title")
            if not isinstance(title, str) or not title.strip():
                return False
            position = entry.get("position")
            if position is not None and not isinstance(position, int):
                return False
            duration_seconds = entry.get("duration_seconds")
            if duration_seconds is not None and not isinstance(duration_seconds, int):
                return False
            artist = entry.get("artist")
            if artist is not None and not isinstance(artist, str):
                return False
            disc_number = entry.get("disc_number")
            if disc_number is not None and not isinstance(disc_number, int):
                return False
        return True
    return True


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
    if cleaned:
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