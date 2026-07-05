from collections.abc import Mapping
from typing import Any

from app.catalog.metadata_fields import editable_field_keys
from app.metadata_normalized import ALLOWED_NORMALIZED_METADATA_KEYS

_PROPOSAL_ROOT_ALLOWLIST = editable_field_keys() | {
    "candidate_type",
    "kind",
    "normalized",
    "release_type",
}
_PROPOSAL_NORMALIZED_ALLOWLIST = ALLOWED_NORMALIZED_METADATA_KEYS | {
    "candidate_type",
    "kind",
    "release_type",
    "schema_version",
}


def compact_metadata_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    compacted = _compact_json_like(payload)
    if isinstance(compacted, dict) and compacted:
        return compacted
    return None


def validate_metadata_payload(payload: Mapping[str, Any] | None) -> None:
    if not isinstance(payload, Mapping):
        return
    for raw_key, raw_value in payload.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError("metadata_payload contains an empty key")
        if key not in _PROPOSAL_ROOT_ALLOWLIST:
            raise ValueError(f"metadata_payload contains unknown key: {key}")
        if key == "normalized":
            _validate_normalized_payload(raw_value)


def _validate_normalized_payload(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        raise ValueError("metadata_payload.normalized must be an object")
    for raw_key in value:
        key = str(raw_key).strip()
        if not key:
            raise ValueError("metadata_payload.normalized contains an empty key")
        if key not in _PROPOSAL_NORMALIZED_ALLOWLIST:
            raise ValueError(f"metadata_payload.normalized contains unknown key: {key}")


def _compact_json_like(value: Any) -> Any:
    if isinstance(value, Mapping):
        compacted: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()
            if not key:
                continue
            normalized = _compact_json_like(raw_value)
            if _is_empty(normalized):
                continue
            compacted[key] = normalized
        return compacted

    if isinstance(value, list):
        compacted_list = []
        for entry in value:
            normalized = _compact_json_like(entry)
            if _is_empty(normalized):
                continue
            compacted_list.append(normalized)
        return compacted_list

    if isinstance(value, str):
        text = value.strip()
        return text if text else None

    return value


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if value == {}:
        return True
    if value == []:
        return True
    return False
