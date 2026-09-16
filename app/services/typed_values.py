"""Persistence helpers for structured values without JSON database columns."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def _escape_pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _unescape_pointer_token(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def flatten_typed_values(value: Any, *, path: str = "") -> list[dict[str, Any]]:
    """Flatten a JSON-like Python value into rows with concrete scalar slots."""

    if isinstance(value, Enum):
        return flatten_typed_values(value.value, path=path)
    if isinstance(value, Mapping):
        rows: list[dict[str, Any]] = [{"path": path, "value_type": "object"}]
        for key, child in value.items():
            child_path = f"{path}/{_escape_pointer_token(str(key))}"
            rows.extend(flatten_typed_values(child, path=child_path))
        return rows
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        rows = [{"path": path, "value_type": "array"}]
        for index, child in enumerate(value):
            rows.extend(flatten_typed_values(child, path=f"{path}/{index}"))
        return rows
    if value is None:
        return [{"path": path, "value_type": "null"}]
    if isinstance(value, bool):
        return [{"path": path, "value_type": "boolean", "boolean_value": value}]
    if isinstance(value, UUID):
        return [{"path": path, "value_type": "uuid", "uuid_value": value}]
    if isinstance(value, datetime):
        return [{"path": path, "value_type": "datetime", "datetime_value": value}]
    if isinstance(value, date):
        return [{"path": path, "value_type": "date", "date_value": value}]
    if isinstance(value, int):
        return [{"path": path, "value_type": "integer", "integer_value": value}]
    if isinstance(value, Decimal):
        return [{"path": path, "value_type": "decimal", "decimal_value": value}]
    if isinstance(value, float):
        return [{"path": path, "value_type": "decimal", "decimal_value": Decimal(str(value))}]
    if isinstance(value, str):
        return [{"path": path, "value_type": "string", "string_value": value}]
    return [{"path": path, "value_type": "string", "string_value": str(value)}]


def typed_value_from_row(row: Any) -> Any:
    def get(name: str, default: Any = None) -> Any:
        if isinstance(row, Mapping):
            return row.get(name, default)
        return getattr(row, name, default)

    value_type = get("value_type")
    if value_type in {"object", "array", "null"}:
        return {} if value_type == "object" else [] if value_type == "array" else None
    return {
        "string": get("string_value"),
        "integer": get("integer_value"),
        "decimal": get("decimal_value"),
        "boolean": get("boolean_value"),
        "date": get("date_value"),
        "datetime": get("datetime_value"),
        "uuid": get("uuid_value"),
    }.get(value_type)


def materialize_typed_values(rows: Sequence[Any]) -> Any:
    """Rebuild a nested mapping/list from rows using JSON Pointer paths."""

    if not rows:
        return {}

    def path_for(row: Any) -> str:
        if isinstance(row, Mapping):
            return str(row.get("path") or "")
        return row.path

    def tokens_for(path: str) -> list[str]:
        if not path:
            return []
        raw_tokens = path[1:].split("/") if path.startswith("/") else path.split("/")
        return [_unescape_pointer_token(token) for token in raw_tokens]

    ordered = sorted(rows, key=lambda row: (path_for(row).count("/"), path_for(row)))
    root: Any = typed_value_from_row(ordered[0]) if path_for(ordered[0]) == "" else None

    for row in ordered:
        tokens = tokens_for(path_for(row))
        if not tokens:
            root = typed_value_from_row(row)
            continue
        if root is None:
            root = [] if tokens[0].isdigit() else {}
        current = root
        for index, token in enumerate(tokens):
            is_last = index == len(tokens) - 1
            next_is_list = not is_last and tokens[index + 1].isdigit()
            if isinstance(current, list):
                position = int(token)
                while len(current) <= position:
                    current.append(None)
                if is_last:
                    current[position] = typed_value_from_row(row)
                elif current[position] is None:
                    current[position] = [] if next_is_list else {}
                current = current[position]
            else:
                if is_last:
                    current[token] = typed_value_from_row(row)
                else:
                    current.setdefault(token, [] if next_is_list else {})
                    current = current[token]
    return root
