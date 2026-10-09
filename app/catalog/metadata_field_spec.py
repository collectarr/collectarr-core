"""Shared mechanics for declaring canonical editable metadata fields."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.base import ItemKind

VALUE_TYPE_STRING = "string"
VALUE_TYPE_STRING_LIST = "string_list"
VALUE_TYPE_INTEGER = "integer"
VALUE_TYPE_BOOLEAN = "boolean"
VALUE_TYPE_PARTIAL_DATE = "partial_date"
VALUE_TYPE_LINK_LIST = "link_list"
VALUE_TYPE_OBJECT_LIST = "object_list"

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
PRINT_KINDS: frozenset[ItemKind] = frozenset({ItemKind.book, ItemKind.comic, ItemKind.manga})
TRAILER_KINDS: frozenset[ItemKind] = VIDEO_KINDS | frozenset({ItemKind.game})
ALL_KINDS: frozenset[ItemKind] = frozenset(ItemKind)
CATALOG_KINDS: frozenset[ItemKind] = ALL_KINDS - {ItemKind.collection}


@dataclass(frozen=True)
class MetadataFieldSpec:
    """Kind-owned field identity, type, applicability, and UI hints."""

    key: str
    value_type: str
    label: str
    editable: bool = True
    section: str = SECTION_ITEM
    input: str = INPUT_TEXT
    kinds: frozenset[ItemKind] = field(default_factory=frozenset)
    correction_only: bool = False

    def applies_to(self, kind: ItemKind) -> bool:
        return kind in self.kinds


@dataclass(frozen=True)
class NormalizedFieldSpec:
    """Persistence-normalization behavior separate from edit-field metadata."""

    key: str
    kinds: frozenset[ItemKind]
    typed: bool = False
    common: bool = False

    def applies_to(self, kind: ItemKind) -> bool:
        return kind in self.kinds
