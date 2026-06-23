from collections.abc import Mapping
from typing import Any


def compact_metadata_payload(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    compacted = _compact_json_like(payload)
    if isinstance(compacted, dict) and compacted:
        return compacted
    return None


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
