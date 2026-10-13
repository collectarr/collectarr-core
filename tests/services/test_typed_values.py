from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.services.typed_values import (
    flatten_typed_values,
    materialize_typed_values,
    typed_value_from_row,
)


def test_typed_values_round_trip_preserves_scalar_types() -> None:
    value = {
        "title": "The Hobbit",
        "published": date(1937, 9, 21),
        "imported_at": datetime(2026, 9, 16, 12, 30),
        "score": Decimal("9.25"),
        "ids": [UUID("11111111-1111-1111-1111-111111111111")],
    }

    rows = flatten_typed_values(value)

    assert materialize_typed_values(rows) == value


def test_typed_values_escape_object_keys_and_restore_arrays() -> None:
    value = {"a/b": {"tilde~key": ["first", "second"]}}

    rows = flatten_typed_values(value)

    assert materialize_typed_values(rows) == value
    assert {row["path"] for row in rows} == {
        "",
        "/a~1b",
        "/a~1b/tilde~0key",
        "/a~1b/tilde~0key/0",
        "/a~1b/tilde~0key/1",
    }


def test_typed_value_from_row_rejects_values_in_the_wrong_slot() -> None:
    row = {
        "value_type": "integer",
        "integer_value": "not an integer",
        "string_value": "ignored",
    }

    assert typed_value_from_row(row) is None
