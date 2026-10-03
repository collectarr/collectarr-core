"""Shared mechanics for declaring canonical editable metadata fields."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.catalog.grouping_models import PRINT_GROUPING_KINDS
from app.models.base import ItemKind

VALUE_TYPE_STRING = "string"
VALUE_TYPE_STRING_LIST = "string_list"
VALUE_TYPE_INTEGER = "integer"
VALUE_TYPE_BOOLEAN = "boolean"
VALUE_TYPE_PARTIAL_DATE = "partial_date"
VALUE_TYPE_LINK_LIST = "link_list"

SECTION_ITEM = "item"
SECTION_PUBLISHING = "publishing"
SECTION_TECHNICAL = "technical"
SECTION_REGIONAL = "regional"
SECTION_ARTWORK = "artwork"
SECTION_RELATIONS = "relations"
SECTION_INTERNAL = "internal"

INPUT_TEXT = "text"
INPUT_MULTILINE = "multiline"
INPUT_NUMBER = "number"
INPUT_DATE = "date"
INPUT_LIST = "list"

VIDEO_KINDS: frozenset[ItemKind] = frozenset({ItemKind.anime, ItemKind.movie, ItemKind.tv})
PRINT_KINDS: frozenset[ItemKind] = PRINT_GROUPING_KINDS
TRAILER_KINDS: frozenset[ItemKind] = VIDEO_KINDS | frozenset({ItemKind.game})
ALL_KINDS: frozenset[ItemKind] = frozenset(ItemKind)


@dataclass(frozen=True)
class MetadataFieldSpec:
    """One canonical field's schema and presentation hints."""

    key: str
    value_type: str
    label: str
    common: bool = False
    typed: bool = False
    normalized: bool = False
    editable: bool = True
    section: str = SECTION_ITEM
    input: str = INPUT_TEXT
    kinds: frozenset[ItemKind] = field(default_factory=frozenset)

    def applies_to(self, kind: ItemKind) -> bool:
        if self.key == "physical_format" and kind is ItemKind.music:
            return False
        return self.common or kind in self.kinds

    def scope_for_kind(self, kind: ItemKind) -> str:
        from app.catalog.metadata_fields import _scope_for_kind

        return _scope_for_kind(kind, self.key)

    def write_target_for_kind(self, kind: ItemKind) -> str:
        from app.catalog.metadata_fields import _field_write_target

        return _field_write_target(self.key, kind)

    def source_entity_type_for_kind(self, kind: ItemKind) -> str:
        from app.catalog.metadata_fields import _field_source_entity_type

        return _field_source_entity_type(self.key, kind)

    def source_table_for_kind(self, kind: ItemKind) -> str:
        from app.catalog.metadata_fields import _field_source_table

        return _field_source_table(self.key, kind)
