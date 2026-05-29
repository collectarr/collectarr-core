from collections.abc import Mapping
from typing import Any


ALLOWED_NORMALIZED_METADATA_KEYS = {
    "associated_image_id",
    "audience_rating",
    "cover_delivery_url",
    "cover_policy",
    "cover_source_url",
    "cover_status",
    "cover_storage",
    "genres",
    "physical_format",
    "physical_format_label",
    "physical_format_media_family",
    "physical_format_variant_type",
    "platforms",
    "track_count",
    "tracks",
}


def clean_normalized_metadata(values: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(values, Mapping):
        return {}
    return {
        str(key): value
        for key, value in values.items()
        if str(key) in ALLOWED_NORMALIZED_METADATA_KEYS and value is not None and value != [] and value != {}
    }


def set_normalized_metadata(
    metadata_json: Mapping[str, Any] | None,
    normalized_values: Mapping[str, Any] | None,
) -> dict[str, Any]:
    metadata = dict(metadata_json or {})
    normalized = clean_normalized_metadata(normalized_values)
    if normalized:
        metadata["normalized"] = normalized
    else:
        metadata.pop("normalized", None)
    return metadata


def merge_normalized_metadata(
    metadata_json: Mapping[str, Any] | None,
    updates: Mapping[str, Any] | None,
) -> dict[str, Any]:
    metadata = dict(metadata_json or {})
    current = metadata.get("normalized")
    merged = dict(current) if isinstance(current, dict) else {}
    if isinstance(updates, Mapping):
        merged.update(dict(updates))
    return set_normalized_metadata(metadata, merged)