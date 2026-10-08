"""Reusable structure for kind-owned Catalog Item document schemas."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChildObjectShape:
    """Typed fields and validation rules for one contained object."""

    fields: Mapping[str, str]
    nested: Mapping[str, ChildObjectShape] = field(default_factory=dict)
    required: frozenset[str] = frozenset()
    non_empty: frozenset[str] = frozenset()
    nullable: frozenset[str] = frozenset()
    allow_string_value: bool = False
    validate_collection: Callable[[list[Mapping[str, Any]], str], None] | None = None


@dataclass(frozen=True)
class KindDocumentShape:
    """Kind-owned root fields and contained-object schemas."""

    # Additional scalar root fields not already declared by the edit-field
    # registry. Their mapping key is the field name and value is its schema
    # value type.
    root_fields: Mapping[str, str]
    children: Mapping[str, ChildObjectShape]
    root_field_overrides: Mapping[str, str] = field(default_factory=dict)
    rejected_root_fields: frozenset[str] = frozenset()
    allowed_root_fields: frozenset[str] | None = None
    validate_document: Callable[[Mapping[str, Any], str], None] | None = None
    required_root_fields: frozenset[str] = frozenset()


STRING = "string"
INTEGER = "integer"
BOOLEAN = "boolean"
STRING_LIST = "string_list"
INTEGER_LIST = "integer_list"
PARTIAL_DATE = "partial_date"
PARTIAL_DATE_OBJECT = "partial_date_object"
INTEGER_OR_STRING = "integer_or_string"


PERSON = ChildObjectShape(
    fields={
        "id": STRING,
        "person_id": STRING,
        "name": STRING,
        "role": STRING,
        "role_id": STRING,
        "sequence": INTEGER,
        "credited_name": STRING,
        "image_url": STRING,
        "sort_name": STRING,
    },
    nullable=frozenset({"id", "person_id", "sequence"}),
    allow_string_value=True,
)

IDENTIFIER = ChildObjectShape(
    fields={
        "id": STRING,
        "identifier_type": STRING,
        "value": STRING,
        "normalized_value": STRING,
        "is_primary": BOOLEAN,
    },
    required=frozenset({"identifier_type", "value"}),
    non_empty=frozenset({"identifier_type", "value"}),
    nullable=frozenset({"id", "normalized_value", "is_primary"}),
    allow_string_value=True,
)

LINK = ChildObjectShape(
    fields={
        "id": STRING,
        "label": STRING,
        "title": STRING,
        "url": STRING,
        "site": STRING,
        "name": STRING,
        "kind": STRING,
        "description": STRING,
        "position": INTEGER,
        "link_type": STRING,
    },
    nullable=frozenset({"id", "position"}),
)

CHARACTER = ChildObjectShape(
    fields={
        "id": STRING,
        "character_id": STRING,
        "name": STRING,
        "aliases": STRING_LIST,
        "role": STRING,
        "description": STRING,
        "image_url": STRING,
    },
    nullable=frozenset({"id", "character_id", "aliases"}),
    allow_string_value=True,
)

STORY_ARC = ChildObjectShape(
    fields={
        "id": STRING,
        "story_arc_id": STRING,
        "name": STRING,
        "description": STRING,
        "publisher": STRING,
        "start_date": PARTIAL_DATE,
        "end_date": PARTIAL_DATE,
    },
    nullable=frozenset({"id", "story_arc_id", "start_date", "end_date"}),
    allow_string_value=True,
)

LABEL = ChildObjectShape(
    fields={
        "label_id": STRING,
        "label_name": STRING,
        "catalog_number": STRING,
        "sequence": INTEGER,
    },
    nullable=frozenset({"label_id", "sequence"}),
)


def partial_date_schema() -> dict[str, Any]:
    return {
        "anyOf": [
            {"type": "string"},
            partial_date_object_schema(),
        ]
    }


def partial_date_object_schema(*, allow_empty: bool = True) -> dict[str, Any]:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "year": {"type": "integer", "minimum": 1, "maximum": 9999},
            "month": {"type": "integer", "minimum": 1, "maximum": 12},
            "day": {"type": "integer", "minimum": 1, "maximum": 31},
        },
    }
    if not allow_empty:
        schema["minProperties"] = 1
    return schema
