"""Kind-aware validation for flattened Catalog Item JSON payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.catalog.metadata_fields import MetadataFieldSpec, fields_for_kind
from app.models.base import ItemKind

# The field registry owns scalar/root catalog fields. These additions are
# kind-owned values and contained children that are not scalar metadata fields.
_KIND_ROOT_FIELDS: dict[ItemKind, frozenset[str]] = {
    ItemKind.anime: frozenset(
        {
            "description",
            "creators",
            "contributors",
            "characters",
            "character_details",
            "seasons",
            "episodes",
            "discs",
            "media",
        }
    ),
    ItemKind.boardgame: frozenset(
        {
            "contributors",
            "description",
            "identifiers",
            "min_players",
            "max_players",
            "playing_time_minutes",
            "min_age",
            "year_published",
        }
    ),
    ItemKind.book: frozenset(
        {
            "creators",
            "contributors",
            "description",
            "identifiers",
            "printings",
            "series_title",
            "volume_name",
            "volume_number",
            "isbn",
            "isbn10",
            "isbn13",
        }
    ),
    ItemKind.comic: frozenset(
        {
            "creators",
            "contributors",
            "description",
            "characters",
            "character_details",
            "story_arcs",
            "identifiers",
            "series_title",
            "volume_name",
            "issue_number",
            "cover_price_cents",
            "currency",
            "key_comic",
            "key_reason",
        }
    ),
    ItemKind.game: frozenset(
        {
            "creators",
            "contributors",
            "description",
            "identifiers",
            "platforms",
            "developers",
            "company_roles",
            "series_title",
            "release_region",
        }
    ),
    ItemKind.manga: frozenset(
        {
            "creators",
            "contributors",
            "description",
            "characters",
            "chapters",
            "character_details",
            "identifiers",
            "series_title",
            "volume_name",
            "volume_number",
            "isbn",
            "isbn10",
            "isbn13",
        }
    ),
    ItemKind.movie: frozenset(
        {
            "description",
            "creators",
            "contributors",
            "characters",
            "character_details",
            "discs",
            "media",
        }
    ),
    ItemKind.music: frozenset(
        {
            "subtitle",
            "sort_title",
            "original_release_date",
            "original_release_date_parts",
            "label",
            "format",
            "artist_credits",
            "composers",
            "conductors",
            "choruses",
            "compositions",
            "orchestras",
            "songwriters",
            "producers",
            "engineers",
            "musicians",
            "recording_date",
            "recording_date_parts",
            "studios",
            "sound_types",
            "is_live",
            "packaging",
            "vinyl_color",
            "vinyl_weight",
            "rpm",
            "extra",
            "spars",
            "box_set",
            "discs",
        }
    ),
    ItemKind.tv: frozenset(
        {
            "description",
            "creators",
            "contributors",
            "characters",
            "character_details",
            "seasons",
            "episodes",
            "discs",
            "media",
        }
    ),
}
_COMMON_ROOT_FIELDS = frozenset({"release_date_parts"})
_ADDITIONAL_ROOT_VALUE_TYPES: dict[str, str] = {
    "description": "string",
    "min_players": "integer",
    "max_players": "integer",
    "playing_time_minutes": "integer",
    "min_age": "integer",
    "year_published": "integer",
    "issue_number": "string",
    "cover_price_cents": "integer",
    "currency": "string",
    "key_comic": "boolean",
    "key_reason": "string",
    "series_title": "string",
    "volume_name": "string",
    "volume_number": "string",
    "isbn": "string",
    "isbn10": "string",
    "isbn13": "string",
    "release_region": "string",
    "developers": "string_list",
    "sort_title": "string",
    "format": "string",
    "label": "string",
    "subtitle": "string",
    "back_cover_image_url": "string",
    "recording_date": "partial_date",
    "recording_date_parts": "partial_date",
    "original_release_date": "partial_date",
    "original_release_date_parts": "partial_date",
    "is_live": "boolean",
    "packaging": "string",
    "studios": "string_list",
    "sound_types": "string_list",
    "vinyl_color": "string",
    "vinyl_weight": "string",
    "rpm": "integer",
    "extra": "string",
    "spars": "string",
    "box_set": "string",
    "choruses": "string_list",
    "compositions": "string_list",
    "orchestras": "string_list",
    "release_date_parts": "partial_date",
}
_INTEGER_CHILD_FIELDS = frozenset(
    {
        "sequence",
        "position",
        "disc_number",
        "medium_number",
        "media_number",
        "track_count",
        "expected_track_count",
        "duration_ms",
        "num_discs",
        "nr_layers",
        "duration_seconds",
        "indent_level",
        "offset_ms",
        "bitrate_kbps",
        "file_size_bytes",
        "season_number",
        "episode_number",
        "runtime_minutes",
        "page_count",
        "printing_number",
        "chapter_number",
    }
)
_BOOLEAN_CHILD_FIELDS = frozenset({"is_header", "is_primary"})
_STRING_LIST_CHILD_FIELDS = frozenset({"aliases"})
_INTEGER_LIST_CHILD_FIELDS = frozenset({"missing_track_positions"})
_DATE_CHILD_FIELDS = frozenset({"air_date", "release_date", "start_date", "end_date"})

_PERSON_FIELDS = frozenset(
    {
        "person_id",
        "artist_id",
        "name",
        "role",
        "role_id",
        "sequence",
        "credited_name",
        "join_phrase",
        "image_url",
    }
)
_MUSIC_CREDIT_FIELDS = frozenset(
    {"name", "role", "credited_name", "join_phrase", "sequence", "instrument"}
)
_MUSIC_TRACK_FIELDS = frozenset({"position", "title", "artist", "duration_ms"})
_MUSIC_DISC_FIELDS = frozenset(
    {"disc_number", "title", "matrix_number_side_a", "matrix_number_side_b", "tracks"}
)
_MUSIC_REQUIRED_CHILD_FIELDS: dict[str, frozenset[str]] = {
    "discs": frozenset({"disc_number"}),
    "tracks": frozenset({"title"}),
}
_MOVIE_REQUIRED_CHILD_FIELDS: dict[str, frozenset[str]] = {
    "media": frozenset({"media_number"}),
}
_BOOK_REQUIRED_CHILD_FIELDS: dict[str, frozenset[str]] = {
    "creators": frozenset({"name"}),
    "contributors": frozenset({"name"}),
    "identifiers": frozenset({"identifier_type", "value"}),
}
_TRACK_FIELDS = frozenset(
    {
        "position",
        "track_number",
        "title",
        "duration",
        "duration_seconds",
        "disc_number",
        "artist",
        "recording_id",
        "is_header",
        "indent_level",
        "parent_header_id",
        "duration_ms",
        "offset_ms",
        "bitrate_kbps",
        "file_size_bytes",
        "instrument",
        "composition",
    }
)
_DISC_FIELDS = frozenset(
    {
        "disc_number",
        "medium_number",
        "medium_type",
        "title",
        "name",
        "track_count",
        "expected_track_count",
        "sound_type",
        "vinyl_color",
        "vinyl_weight",
        "rpm",
        "spars",
        "missing_track_positions",
        "tracks",
    }
)
_MOVIE_MEDIA_FIELDS = frozenset(
    {
        "media_number",
        "media_type",
        "title",
        "aspect_ratio",
        "screen_ratio",
        "color",
        "num_discs",
        "nr_layers",
        "layers",
        "audio_tracks",
        "subtitles",
    }
)
_EPISODE_FIELDS = frozenset(
    {
        "season_number",
        "episode_number",
        "episode_title",
        "title",
        "description",
        "overview",
        "air_date",
        "runtime_minutes",
        "page_count",
        "position",
    }
)
_SEASON_FIELDS = frozenset(
    {"season_number", "title", "description", "air_date", "episode_count", "episodes"}
)
_CHAPTER_FIELDS = frozenset({"chapter_number", "title", "release_date", "page_count", "position"})
_PRINTING_FIELDS = frozenset(
    {"printing_number", "title", "release_date", "publisher", "language", "isbn"}
)
_IDENTIFIER_FIELDS = frozenset({"identifier_type", "value", "normalized_value", "is_primary"})
_LINK_FIELDS = frozenset(
    {
        "label",
        "title",
        "url",
        "site",
        "name",
        "kind",
        "description",
        "position",
        "link_type",
    }
)
_CHARACTER_FIELDS = frozenset(
    {"character_id", "name", "aliases", "role", "description", "image_url"}
)
_STORY_ARC_FIELDS = frozenset(
    {
        "story_arc_id",
        "name",
        "description",
        "publisher",
        "start_date",
        "end_date",
    }
)

_CHILD_FIELDS: dict[str, frozenset[str]] = {
    "contributors": _PERSON_FIELDS,
    "creators": _PERSON_FIELDS,
    "artist_credits": _PERSON_FIELDS,
    "tracks": _TRACK_FIELDS,
    "discs": _DISC_FIELDS,
    "media": _DISC_FIELDS,
    "episodes": _EPISODE_FIELDS,
    "seasons": _SEASON_FIELDS,
    "chapters": _CHAPTER_FIELDS,
    "printings": _PRINTING_FIELDS,
    "identifiers": _IDENTIFIER_FIELDS,
    "external_links": _LINK_FIELDS,
    "trailer_urls": _LINK_FIELDS,
    "characters": _CHARACTER_FIELDS,
    "character_details": _CHARACTER_FIELDS,
    "story_arcs": _STORY_ARC_FIELDS,
    "labels": frozenset({"label_id", "label_name", "catalog_number", "sequence"}),
}

_MUSIC_CREDIT_LISTS = frozenset(
    {
        "artist_credits",
        "composers",
        "conductors",
        "songwriters",
        "producers",
        "engineers",
        "musicians",
    }
)


def catalog_item_payload_contract() -> dict[str, Any]:
    """Return the v1 JSON Schema for every kind's flattened proposal payload."""
    kinds: dict[str, Any] = {}
    for kind in ItemKind:
        if kind is ItemKind.collection:
            continue
        field_specs = {spec.key: spec for spec in fields_for_kind(kind, editable_only=True)}
        root_fields = _root_fields_for_kind(kind, field_specs)
        properties = {
            key: _json_schema_for_root_field(key, kind, field_specs) for key in sorted(root_fields)
        }
        kinds[kind.value] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["title"],
            "properties": properties,
        }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://schemas.collectarr.app/catalog-item/v1",
        "title": "Collectarr Flattened Catalog Item v1 Proposal Payloads",
        "description": (
            "Proposal shape retained after Core projects submissions onto fields "
            "recognized for the declared kind. Unknown incoming fields are omitted."
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
    """Validate and retain only Core-recognized fields for this item kind."""
    if kind is ItemKind.collection:
        raise ValueError("Collection is not a Catalog Item kind")

    field_specs = {spec.key: spec for spec in fields_for_kind(kind, editable_only=True)}
    root_fields = _root_fields_for_kind(kind, field_specs)
    return _project_object(
        payload,
        root_fields,
        "catalog_item",
        field_specs=field_specs,
        additional_value_types=_ADDITIONAL_ROOT_VALUE_TYPES,
        kind=kind,
    )


def _root_fields_for_kind(
    kind: ItemKind,
    field_specs: Mapping[str, MetadataFieldSpec],
) -> set[str]:
    root_fields = set(field_specs)
    root_fields.update(_COMMON_ROOT_FIELDS)
    root_fields.update(_KIND_ROOT_FIELDS[kind])
    if kind is ItemKind.music:
        # Music v1 is grounded in the saved CLZ form. Do not inherit obsolete
        # release-group/provider fields from the transitional metadata registry.
        return {
            "title",
            "release_date",
            "release_date_parts",
            "genres",
            "barcode",
            "catalog_number",
            "country",
            "cover_image_url",
            "back_cover_image_url",
            "thumbnail_image_url",
            "external_links",
            *_KIND_ROOT_FIELDS[kind],
        }
    return root_fields


def _json_schema_for_root_field(
    key: str,
    kind: ItemKind,
    field_specs: Mapping[str, MetadataFieldSpec],
) -> dict[str, Any]:
    if key == "title":
        return {"type": "string", "minLength": 1, "maxLength": 255}
    child_fields = _child_fields_for_kind(key, kind)
    if child_fields is not None:
        return _nullable_schema(
            {
                "type": "array",
                "items": _json_schema_for_child(key, kind, child_fields),
            }
        )
    spec = field_specs.get(key)
    value_type = spec.value_type if spec is not None else _ADDITIONAL_ROOT_VALUE_TYPES.get(key)
    return _nullable_schema(_json_schema_for_value_type(value_type))


def _json_schema_for_child(
    child_key: str,
    kind: ItemKind,
    fields: frozenset[str],
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for key in sorted(fields):
        nested = _child_fields_for_kind(key, kind)
        if nested is not None:
            properties[key] = _nullable_schema(
                {
                    "type": "array",
                    "items": _json_schema_for_child(key, kind, nested),
                }
            )
        elif key in _INTEGER_CHILD_FIELDS:
            if kind is ItemKind.music and child_key == "tracks" and key == "position":
                properties[key] = _nullable_schema(
                    {"anyOf": [{"type": "integer"}, {"type": "string"}]}
                )
                continue
            integer_schema: dict[str, Any] = {"type": "integer"}
            if kind is ItemKind.music and key == "disc_number":
                integer_schema["minimum"] = 1
            if kind is ItemKind.movie and child_key == "media" and key == "media_number":
                integer_schema["minimum"] = 1
                properties[key] = integer_schema
            else:
                properties[key] = _nullable_schema(integer_schema)
        elif key in _BOOLEAN_CHILD_FIELDS:
            properties[key] = _nullable_schema({"type": "boolean"})
        elif key in _STRING_LIST_CHILD_FIELDS:
            properties[key] = _nullable_schema({"type": "array", "items": {"type": "string"}})
        elif key in _INTEGER_LIST_CHILD_FIELDS:
            properties[key] = _nullable_schema({"type": "array", "items": {"type": "integer"}})
        elif key in _DATE_CHILD_FIELDS:
            properties[key] = _nullable_schema(_json_schema_for_value_type("partial_date"))
        elif key == "instrument" and kind is ItemKind.music:
            properties[key] = _nullable_schema({"type": "string"})
        else:
            string_schema: dict[str, Any] = {"type": "string"}
            if kind is ItemKind.music and child_key == "tracks" and key == "title":
                string_schema["minLength"] = 1
            properties[key] = _nullable_schema(string_schema)
    object_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }
    if kind is ItemKind.music:
        required = _MUSIC_REQUIRED_CHILD_FIELDS.get(child_key)
        if required:
            object_schema["required"] = sorted(required)
    if kind is ItemKind.movie:
        required = _MOVIE_REQUIRED_CHILD_FIELDS.get(child_key)
        if required:
            object_schema["required"] = sorted(required)
    if kind is ItemKind.book:
        required = _BOOK_REQUIRED_CHILD_FIELDS.get(child_key)
        if required:
            object_schema["required"] = sorted(required)
    if child_key in _MUSIC_CREDIT_LISTS:
        return {"anyOf": [{"type": "string"}, object_schema]}
    if kind is not ItemKind.music and child_key in {
        "characters",
        "story_arcs",
        "contributors",
        "creators",
        "identifiers",
    }:
        return {"anyOf": [{"type": "string"}, object_schema]}
    return object_schema


def _child_fields_for_kind(
    key: str,
    kind: ItemKind,
) -> frozenset[str] | None:
    if kind is ItemKind.music:
        if key in _MUSIC_CREDIT_LISTS:
            return _MUSIC_CREDIT_FIELDS
        if key == "discs":
            return _MUSIC_DISC_FIELDS
        if key == "tracks":
            return _MUSIC_TRACK_FIELDS
    if kind is ItemKind.movie and key == "media":
        return _MOVIE_MEDIA_FIELDS
    return _CHILD_FIELDS.get(key)


def _json_schema_for_value_type(value_type: str | None) -> dict[str, Any]:
    if value_type in {"string", "integer", "boolean"}:
        return {"type": value_type}
    if value_type == "string_list":
        return {"type": "array", "items": {"type": "string"}}
    if value_type == "link_list":
        return {
            "type": "array",
            "items": _json_schema_for_child("external_links", ItemKind.music, _LINK_FIELDS),
        }
    if value_type == "partial_date":
        return {
            "anyOf": [
                {"type": "string"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "year": {"type": "integer"},
                        "month": {"type": "integer"},
                        "day": {"type": "integer"},
                    },
                },
            ]
        }
    return {}


def _nullable_schema(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _project_object(
    value: Mapping[str, Any],
    allowed_fields: frozenset[str] | set[str],
    path: str,
    *,
    field_specs: Mapping[str, MetadataFieldSpec] | None = None,
    additional_value_types: Mapping[str, str] | None = None,
    strict_child_fields: bool = False,
    kind: ItemKind | None = None,
) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key, child in value.items():
        field_path = f"{path}.{key}"
        if key not in allowed_fields:
            continue

        child_fields = _child_fields_for_kind(key, kind) if kind is not None else _CHILD_FIELDS.get(key)
        if child_fields is None:
            spec = field_specs.get(key) if field_specs is not None else None
            _validate_leaf_value(
                child,
                field_path,
                value_type=(
                    spec.value_type if spec is not None else (additional_value_types or {}).get(key)
                ),
                field_name=key,
                strict_string=strict_child_fields,
                allow_integer_or_string=(
                    kind is ItemKind.music and key == "position" and strict_child_fields
                ),
            )
            projected[key] = child
            continue
        if child is None and kind is ItemKind.movie and key == "media":
            projected[key] = None
            continue
        if not isinstance(child, list):
            raise ValueError(f"{field_path} must be a list")
        entries: list[Any] = []
        for index, entry in enumerate(child):
            entry_path = f"{field_path}[{index}]"
            if isinstance(entry, str) and (
                key
                in {
                    "characters",
                    "story_arcs",
                    "contributors",
                    "creators",
                    "identifiers",
                }
                or (kind is ItemKind.music and key in _MUSIC_CREDIT_LISTS)
            ):
                if kind is ItemKind.book and key in {"creators", "contributors"} and not entry.strip():
                    raise ValueError(f"{entry_path} must not be empty")
                if kind is ItemKind.book and key == "identifiers" and not entry.strip():
                    raise ValueError(f"{entry_path} must not be empty")
                entries.append(entry)
                continue
            if not isinstance(entry, Mapping):
                raise ValueError(f"{entry_path} must be an object")
            if kind is ItemKind.music:
                missing = _MUSIC_REQUIRED_CHILD_FIELDS.get(key, frozenset()) - set(entry)
                if missing:
                    required = ", ".join(sorted(missing))
                    raise ValueError(f"{entry_path} must include {required}")
                if key == "tracks" and not str(entry.get("title", "")).strip():
                    raise ValueError(f"{entry_path}.title must not be empty")
                if key == "discs" and (
                    not isinstance(entry.get("disc_number"), int)
                    or isinstance(entry.get("disc_number"), bool)
                    or entry["disc_number"] < 1
                ):
                    raise ValueError(f"{entry_path}.disc_number must be a positive integer")
            if kind is ItemKind.book:
                missing = _BOOK_REQUIRED_CHILD_FIELDS.get(key, frozenset()) - set(entry)
                if missing:
                    required = ", ".join(sorted(missing))
                    raise ValueError(f"{entry_path} must include {required}")
                for required_key in _BOOK_REQUIRED_CHILD_FIELDS.get(key, frozenset()):
                    required_value = entry.get(required_key)
                    if not isinstance(required_value, str) or not required_value.strip():
                        raise ValueError(f"{entry_path}.{required_key} must not be empty")
            entries.append(
                _project_object(
                    entry,
                    child_fields,
                    entry_path,
                    strict_child_fields=True,
                    kind=kind,
                )
            )
        if kind is ItemKind.movie and key == "media":
            media_numbers: set[int] = set()
            for index, entry in enumerate(entries):
                media_number = entry.get("media_number")
                if (
                    not isinstance(media_number, int)
                    or isinstance(media_number, bool)
                    or media_number < 1
                ):
                    raise ValueError(
                        f"{path}.{key}[{index}].media_number must be a positive integer"
                    )
                if media_number in media_numbers:
                    raise ValueError(
                        f"{path}.{key}[{index}].media_number must be unique"
                    )
                media_numbers.add(media_number)
        projected[key] = entries
    return projected


def _validate_leaf_value(
    value: Any,
    path: str,
    *,
    value_type: str | None,
    field_name: str | None = None,
    strict_string: bool = False,
    allow_integer_or_string: bool = False,
) -> None:
    if value is None:
        return
    if field_name in _INTEGER_CHILD_FIELDS:
        if allow_integer_or_string and isinstance(value, str):
            return
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{path} must be an integer")
        return
    if field_name in _BOOLEAN_CHILD_FIELDS:
        if not isinstance(value, bool):
            raise ValueError(f"{path} must be a boolean")
        return
    if field_name in _INTEGER_LIST_CHILD_FIELDS:
        if not isinstance(value, list) or any(
            not isinstance(item, int) or isinstance(item, bool) for item in value
        ):
            raise ValueError(f"{path} must be a list of integers")
        return
    if field_name in _STRING_LIST_CHILD_FIELDS:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{path} must be a list of strings")
        return
    if field_name in _DATE_CHILD_FIELDS:
        _validate_leaf_value(value, path, value_type="partial_date")
        return
    if value_type == "string" and not isinstance(value, str):
        raise ValueError(f"{path} must be a string")
    if value_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise ValueError(f"{path} must be an integer")
    if value_type == "boolean" and not isinstance(value, bool):
        raise ValueError(f"{path} must be a boolean")
    if value_type == "string_list":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{path} must be a list of strings")
        return
    if value_type == "partial_date":
        if isinstance(value, str):
            return
        if isinstance(value, Mapping) and set(value).issubset({"year", "month", "day"}):
            if any(not isinstance(part, int) or isinstance(part, bool) for part in value.values()):
                raise ValueError(f"{path} date components must be integers")
            return
        raise ValueError(f"{path} must be a partial date string or object")
    if isinstance(value, Mapping):
        field_name = path.rsplit(".", maxsplit=1)[-1]
        if field_name.endswith(("_date", "_date_parts")) and set(value).issubset(
            {"year", "month", "day"}
        ):
            if any(not isinstance(part, int) or isinstance(part, bool) for part in value.values()):
                raise ValueError(f"{path} date components must be integers")
            return
        raise ValueError(f"{path} must use a declared child-object schema")
    if isinstance(value, list) and any(isinstance(item, (Mapping, list)) for item in value):
        raise ValueError(f"{path} contains an undeclared object value")
    if strict_string and not isinstance(value, str):
        raise ValueError(f"{path} must be a string")
