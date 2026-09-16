"""Concrete types for JSON-shaped values crossing application boundaries."""

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | dict[str, JsonValue] | list[JsonValue]
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]
