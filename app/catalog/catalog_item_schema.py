"""Compose and validate kind-owned Catalog Item document schemas."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.catalog.document_shape import (
    BOOLEAN,
    INTEGER,
    INTEGER_LIST,
    INTEGER_OR_STRING,
    PARTIAL_DATE,
    STRING,
    STRING_LIST,
    ChildObjectShape,
    KindDocumentShape,
    partial_date_schema,
)
from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS, catalog_kind_for
from app.catalog.metadata_fields import MetadataFieldSpec, fields_for_kind
from app.models.base import ItemKind


def catalog_item_payload_contract() -> dict[str, Any]:
    """Return the v1 JSON Schema for each kind's proposal document."""
    kinds: dict[str, Any] = {}
    for definition in CATALOG_KIND_DEFINITIONS:
        kind = definition.kind
        document = definition.document
        field_specs = {spec.key: spec for spec in fields_for_kind(kind, editable_only=True)}
        root_fields = _root_fields_for_kind(document, field_specs)
        properties = {
            key: _root_field_schema(key, document, field_specs) for key in sorted(root_fields)
        }
        kind_schema: dict[str, Any] = {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
        }
        if document.required_root_fields:
            kind_schema["required"] = sorted(document.required_root_fields)
        kinds[kind.value] = kind_schema
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://schemas.collectarr.app/catalog-item/v1",
        "title": "Collectarr Flattened Catalog Item v1 Proposal Payloads",
        "description": (
            "Source-neutral Catalog Item documents. Fields are validated and "
            "projected using the schema owned by the declared kind."
        ),
        "schemaVersion": 1,
        "fieldStatus": {
            "music": "grounded_in_saved_clz_music_edit_form",
            "other_kinds": "provisional_clz_parity_unverified_without_edit_form_captures",
        },
        "kinds": kinds,
    }


def validate_catalog_item_payload(
    kind: ItemKind,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and retain only fields recognized by the declared kind."""
    if kind is ItemKind.collection:
        raise ValueError("Collection is not a Catalog Item kind")
    if not isinstance(payload, Mapping):
        raise ValueError("catalog_item must be an object")

    document = catalog_kind_for(kind).document
    field_specs = {spec.key: spec for spec in fields_for_kind(kind, editable_only=True)}
    projected = _project_object(
        payload,
        _root_fields_for_kind(document, field_specs),
        "catalog_item",
        document=document,
        field_specs=field_specs,
    )
    if document.validate_document is not None:
        document.validate_document(projected, "catalog_item")
    return projected


def _root_fields_for_kind(
    document: KindDocumentShape,
    field_specs: Mapping[str, MetadataFieldSpec],
) -> set[str]:
    if document.allowed_root_fields is not None:
        return set(document.allowed_root_fields)
    return {
        "release_date_parts",
        *field_specs,
        *document.root_fields,
        *document.children,
    }


def _root_field_schema(
    key: str,
    document: KindDocumentShape,
    field_specs: Mapping[str, MetadataFieldSpec],
) -> dict[str, Any]:
    child_shape = document.children.get(key)
    if child_shape is not None:
        return _nullable(
            {
                "type": "array",
                "items": _child_schema(child_shape),
            }
        )
    spec = field_specs.get(key)
    value_type = spec.value_type if spec is not None else document.root_fields.get(key)
    schema = _value_schema(value_type, document)
    if key in document.required_root_fields:
        if value_type == STRING:
            schema = {**schema, "minLength": 1}
        return schema
    return _nullable(schema)


def _child_schema(shape: ChildObjectShape) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for key, value_type in shape.fields.items():
        if key in shape.nested:
            child_schema = {
                "type": "array",
                "items": _child_schema(shape.nested[key]),
            }
        else:
            child_schema = _value_schema(value_type)
        if key in shape.non_empty and value_type == STRING:
            child_schema["minLength"] = 1
        properties[key] = child_schema if key not in shape.nullable else _nullable(child_schema)
    for key, nested_shape in shape.nested.items():
        if key not in properties:
            properties[key] = _nullable({"type": "array", "items": _child_schema(nested_shape)})
    schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if shape.required:
        schema["required"] = sorted(shape.required)
    if shape.allow_string_value:
        return {"anyOf": [{"type": "string"}, schema]}
    return schema


def _value_schema(
    value_type: str | None,
    document: KindDocumentShape | None = None,
) -> dict[str, Any]:
    if value_type in {STRING, INTEGER, BOOLEAN}:
        return {"type": value_type}
    if value_type == "number":
        return {"type": "number"}
    if value_type == STRING_LIST:
        return {"type": "array", "items": {"type": "string"}}
    if value_type == INTEGER_LIST:
        return {"type": "array", "items": {"type": "integer"}}
    if value_type == PARTIAL_DATE:
        return partial_date_schema()
    if value_type == INTEGER_OR_STRING:
        return {"anyOf": [{"type": "integer"}, {"type": "string"}]}
    if value_type == "link_list":
        shape = document.children.get("external_links") if document else None
        if shape is not None:
            return {"type": "array", "items": _child_schema(shape)}
        return {"type": "array", "items": {"type": "object"}}
    return {}


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _project_object(
    value: Mapping[str, Any],
    allowed_fields: set[str] | frozenset[str],
    path: str,
    *,
    document: KindDocumentShape,
    field_specs: Mapping[str, MetadataFieldSpec] | None = None,
) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key, child in value.items():
        if key not in allowed_fields:
            continue
        field_path = f"{path}.{key}"
        child_shape = document.children.get(key)
        if child_shape is None:
            spec = field_specs.get(key) if field_specs is not None else None
            value_type = spec.value_type if spec is not None else document.root_fields.get(key)
            _validate_value(child, field_path, value_type)
            projected[key] = child
            continue
        if child is None:
            projected[key] = None
            continue
        if not isinstance(child, list):
            raise ValueError(f"{field_path} must be a list")
        entries: list[Any] = []
        object_entries: list[Mapping[str, Any]] = []
        for index, entry in enumerate(child):
            entry_path = f"{field_path}[{index}]"
            if isinstance(entry, str) and child_shape.allow_string_value:
                if not entry.strip() and child_shape.required:
                    raise ValueError(f"{entry_path} must not be empty")
                entries.append(entry)
                continue
            if not isinstance(entry, Mapping):
                raise ValueError(f"{entry_path} must be an object")
            object_entries.append(entry)
            entries.append(_project_child(entry, child_shape, entry_path, document))
        validator = child_shape.validate_collection
        if validator is not None:
            validator(object_entries, field_path)
        projected[key] = entries
    for required_key in document.required_root_fields:
        if (
            required_key not in projected
            or projected[required_key] is None
            or (isinstance(projected[required_key], str) and not projected[required_key].strip())
        ):
            raise ValueError(f"{path} must include a non-empty {required_key}")
    return projected


def _project_child(
    value: Mapping[str, Any],
    shape: ChildObjectShape,
    path: str,
    document: KindDocumentShape,
) -> dict[str, Any]:
    missing = shape.required - set(value)
    if missing:
        fields = ", ".join(sorted(missing))
        raise ValueError(f"{path} must include {fields}")
    for key in shape.non_empty:
        required_value = value.get(key)
        if not isinstance(required_value, str) or not required_value.strip():
            raise ValueError(f"{path}.{key} must not be empty")

    projected: dict[str, Any] = {}
    for key, child in value.items():
        if key not in shape.fields and key not in shape.nested:
            continue
        child_path = f"{path}.{key}"
        nested_shape = shape.nested.get(key)
        if nested_shape is not None:
            if child is None:
                projected[key] = None
                continue
            if not isinstance(child, list):
                raise ValueError(f"{child_path} must be a list")
            nested_values: list[Any] = []
            object_values: list[Mapping[str, Any]] = []
            for index, item in enumerate(child):
                item_path = f"{child_path}[{index}]"
                if isinstance(item, str) and nested_shape.allow_string_value:
                    nested_values.append(item)
                elif isinstance(item, Mapping):
                    object_values.append(item)
                    nested_values.append(_project_child(item, nested_shape, item_path, document))
                else:
                    raise ValueError(f"{item_path} must be an object")
            if nested_shape.validate_collection is not None:
                nested_shape.validate_collection(object_values, child_path)
            projected[key] = nested_values
            continue
        value_type = shape.fields[key]
        _validate_value(child, child_path, value_type)
        projected[key] = child
    return projected


def _validate_value(value: Any, path: str, value_type: str | None) -> None:
    if value is None:
        return
    if value_type == STRING and not isinstance(value, str):
        raise ValueError(f"{path} must be a string")
    if value_type == INTEGER and (not isinstance(value, int) or isinstance(value, bool)):
        raise ValueError(f"{path} must be an integer")
    if value_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        raise ValueError(f"{path} must be a number")
    if value_type == BOOLEAN and not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean")
    if value_type == STRING_LIST:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{path} must be a list of strings")
        return
    if value_type == INTEGER_LIST:
        if not isinstance(value, list) or any(
            not isinstance(item, int) or isinstance(item, bool) for item in value
        ):
            raise ValueError(f"{path} must be a list of integers")
        return
    if value_type == INTEGER_OR_STRING:
        if not isinstance(value, (int, str)) or isinstance(value, bool):
            raise ValueError(f"{path} must be an integer or string")
        return
    if value_type == PARTIAL_DATE:
        _validate_partial_date(value, path)
        return
    if isinstance(value, Mapping):
        _validate_partial_date(value, path)
    elif isinstance(value, list) and any(isinstance(item, (Mapping, list)) for item in value):
        raise ValueError(f"{path} contains an undeclared object value")


def _validate_partial_date(value: Any, path: str) -> None:
    if isinstance(value, str):
        return
    if isinstance(value, Mapping) and set(value).issubset({"year", "month", "day"}):
        if any(not isinstance(part, int) or isinstance(part, bool) for part in value.values()):
            raise ValueError(f"{path} date components must be integers")
        return
    raise ValueError(f"{path} must be a partial date string or object")
