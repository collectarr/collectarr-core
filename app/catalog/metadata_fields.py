"""Single source of truth for canonical metadata fields.

Historically the catalog metadata fields were declared in many uncoordinated
places: the core normalization lookups (``_KIND_ALLOWED_KEYS``,
``_NORMALIZED_VALUE_TYPES``, ``TYPED_KIND_METADATA_KEYS``), the admin correction
request schema, and the Flutter app's ``kAdminMetadataScalarFields`` contract.
Adding a field meant editing every copy and forgetting one silently broke
manual catalog editing and correction (see the color metadata regression).

Each kind declares its own fields as :class:`MetadataFieldSpec` values. This
module composes those declarations with shared bookkeeping and truly common
fields, then derives every lookup from the registry. It is the schema that the
admin edit panel and the Flutter app edit dialog render from (exposed at
``GET /api/v1/metadata/field-schema``), so the two surfaces can no longer drift
apart.

Two concerns are modelled by a single spec:

* **Normalization** — the subset of fields flagged ``normalized=True`` feed the
  ``app.metadata_normalized`` allow-lists / value-type / typed-column lookups.
  These derivations are intentionally scoped so editorial fields can be added
  without changing field validation behaviour.
* **Editing UI** — every ``editable=True`` field is rendered in the edit panel,
  grouped by :attr:`MetadataFieldSpec.section` and rendered with the widget hint
  in :attr:`MetadataFieldSpec.input`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.catalog.common_metadata_fields import (
    _EDITABLE_COMMON_FIELDS,
    _EDITORIAL_FIELDS,
    _INTERNAL_COMMON_FIELDS,
)
from app.catalog.kind_documents import boardgame, game
from app.catalog.kind_documents.game_boardgame_fields import FIELD_SPECS as _GAME_BOARDGAME_FIELDS
from app.catalog.kind_documents.music import FIELD_SPECS as _MUSIC_FIELDS
from app.catalog.kind_documents.video_fields import FIELD_SPECS as _VIDEO_FIELDS
from app.catalog.metadata_field_spec import (
    ALL_KINDS,
    INPUT_LIST,
    SECTION_RELATIONS,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

_INTERNAL_DERIVED_KEYS = {
    "format_templateimage",
    "format_scaledimage",
    "country_scaledimage",
    "language_scaledimage",
    "audiencerating_templateimage",
    "region_scaledimage",
    "audio_templateimage",
    "physical_format_label",
    "physical_format_media_family",
    "physical_format_variant_type",
    "associated_image_id",
    "cover_delivery_url",
    "cover_policy",
    "cover_source_url",
    "cover_status",
    "cover_storage",
}


# Canonical source matrix. Item-contained values are stored on each kind root.
CANONICAL_ENTITY_MATRIX: dict[ItemKind, dict[str, tuple[str, str]]] = {
    ItemKind.book: {
        "catalog_item": ("catalog_book_item", "book_items"),
    },
    ItemKind.comic: {
        "catalog_item": ("catalog_comic_item", "comic_items"),
    },
    ItemKind.manga: {
        "catalog_item": ("catalog_manga_item", "manga_items"),
    },
    ItemKind.anime: {
        "catalog_item": ("catalog_anime_item", "anime_items"),
    },
    ItemKind.movie: {
        "catalog_item": ("catalog_movie_item", "movie_items"),
    },
    ItemKind.tv: {
        "catalog_item": ("catalog_tv_item", "tv_items"),
    },
    ItemKind.game: {
        "catalog_item": ("catalog_game_item", "game_items"),
    },
    ItemKind.boardgame: {
        "catalog_item": ("catalog_boardgame_item", "boardgame_items"),
    },
    ItemKind.music: {
        "catalog_item": ("catalog_music_item", "music_items"),
    },
}


def _scope_for_kind(kind: ItemKind, key: str) -> str:
    if key in _INTERNAL_DERIVED_KEYS:
        return "internal"
    if kind not in CANONICAL_ENTITY_MATRIX:
        raise KeyError(f"No canonical field ownership is declared for {kind.value}/{key}.")
    return "catalog_item"


@dataclass(frozen=True)
class CanonicalFieldOwnership:
    """Authoritative source and write boundary for one kind field."""

    scope: str
    entity_type: str
    source_table: str
    write_target: str


def _field_ownership(kind: ItemKind, key: str) -> CanonicalFieldOwnership:
    scope = _scope_for_kind(kind, key)
    # Derived display fields read their inputs from the same typed root.
    source_scope = "catalog_item"
    try:
        entity_type, source_table = CANONICAL_ENTITY_MATRIX[kind][source_scope]
    except KeyError as exc:
        raise KeyError(
            f"Canonical field ownership points to an undeclared source "
            f"entity: {kind.value}/{key} -> {scope}."
        ) from exc
    return CanonicalFieldOwnership(
        scope=scope,
        entity_type=entity_type,
        source_table=source_table,
        write_target=_field_write_target(key, kind),
    )


def _field_source_entity_type(key: str, kind: ItemKind) -> str:
    return _field_ownership(kind, key).entity_type


def _field_source_table(key: str, kind: ItemKind) -> str:
    return _field_ownership(kind, key).source_table


def _field_write_target(key: str, kind: ItemKind) -> str:
    if key in _INTERNAL_DERIVED_KEYS:
        return "readonly_computed"
    return "core_canonical"


def contract_rows(kinds: Iterable[ItemKind] | None = None) -> list[dict[str, object]]:
    active_kinds = tuple(kinds or (kind for kind in ItemKind if kind != ItemKind.collection))
    rows: list[dict[str, object]] = []
    for spec in METADATA_FIELDS:
        applicable_kinds = tuple(kind for kind in active_kinds if spec.applies_to(kind))
        if not spec.common and not applicable_kinds:
            continue
        if spec.common and not applicable_kinds:
            continue
        for kind in applicable_kinds:
            rows.append(
                {
                    "key": spec.key,
                    "kind": kind.value,
                    "label": spec.label,
                    "valueType": spec.value_type,
                    "section": spec.section,
                    "input": spec.input,
                    "editable": spec.editable,
                    "normalized": spec.normalized,
                    "common": spec.common,
                    "typed": spec.typed,
                    "scope": spec.scope_for_kind(kind),
                    "writeTarget": spec.write_target_for_kind(kind),
                    "sourceEntityType": spec.source_entity_type_for_kind(kind),
                    "sourceTable": spec.source_table_for_kind(kind),
                }
            )
    return rows


# --- Normalized kind-scoped, typed fields ------------------------------------
_KIND_FIELDS: tuple[MetadataFieldSpec, ...] = (
    MetadataFieldSpec(
        "genres",
        VALUE_TYPE_STRING_LIST,
        "Genres",
        typed=True,
        normalized=True,
        section=SECTION_RELATIONS,
        input=INPUT_LIST,
        kinds=ALL_KINDS,
    ),
    *_GAME_BOARDGAME_FIELDS[:1],
    *_GAME_BOARDGAME_FIELDS[1:],
    *game.FIELD_SPECS,
    *boardgame.FIELD_SPECS,
    *_VIDEO_FIELDS[:1],
)

#: The canonical registry, ordered (normalized common first, then kind-scoped,
#: then editorial). Internal bookkeeping fields come first so the normalized
#: derivations keep their historical ordering semantics.
METADATA_FIELDS: tuple[MetadataFieldSpec, ...] = (
    _INTERNAL_COMMON_FIELDS
    + _EDITABLE_COMMON_FIELDS
    + _KIND_FIELDS
    + _EDITORIAL_FIELDS
    + _MUSIC_FIELDS
)

_FIELD_BY_KEY: dict[str, MetadataFieldSpec] = {spec.key: spec for spec in METADATA_FIELDS}


def field_spec(key: str) -> MetadataFieldSpec | None:
    return _FIELD_BY_KEY.get(key)


def common_field_keys() -> set[str]:
    """Return normalized fields shared by every canonical kind."""
    return {spec.key for spec in METADATA_FIELDS if spec.normalized and spec.common}


def kind_allowed_keys() -> dict[ItemKind, set[str]]:
    """Per-kind set of non-common normalized field keys."""
    result: dict[ItemKind, set[str]] = {kind: set() for kind in ItemKind}
    for spec in METADATA_FIELDS:
        if not spec.normalized or spec.common:
            continue
        for kind in spec.kinds:
            result[kind].add(spec.key)
    return result


def value_types() -> dict[str, str]:
    """Normalized field value types (mirrors ``_NORMALIZED_VALUE_TYPES``)."""
    return {spec.key: spec.value_type for spec in METADATA_FIELDS if spec.normalized}


def typed_field_keys() -> set[str]:
    """Normalized fields backed by a typed canonical kind table column."""
    return {spec.key for spec in METADATA_FIELDS if spec.normalized and spec.typed}


def fields_for_kind(kind: ItemKind, *, editable_only: bool = False) -> list[MetadataFieldSpec]:
    """Ordered specs for a kind (common + that kind's fields)."""
    return [
        spec
        for spec in METADATA_FIELDS
        if spec.applies_to(kind) and (not editable_only or spec.editable)
    ]


# Materialize the ownership matrix once so every consumer reads the same root
# ownership answer. An applicable field without a declared kind root is an
# error rather than an implicit fallback.
FIELD_OWNERSHIP_MATRIX: dict[ItemKind, dict[str, CanonicalFieldOwnership]] = {
    kind: {spec.key: _field_ownership(kind, spec.key) for spec in fields_for_kind(kind)}
    for kind in ItemKind
    if kind != ItemKind.collection
}


def canonical_field_ownership(kind: ItemKind, key: str) -> CanonicalFieldOwnership:
    """Return the exact ownership declaration for ``kind``/``key``."""

    try:
        return FIELD_OWNERSHIP_MATRIX[kind][key]
    except KeyError as exc:
        raise KeyError(f"No canonical field ownership is declared for {kind.value}/{key}.") from exc


def editable_fields() -> list[MetadataFieldSpec]:
    """All user-editable specs, in registry order."""
    return [spec for spec in METADATA_FIELDS if spec.editable]


def editable_field_keys() -> set[str]:
    """Editable canonical field keys accepted by proposal/correction payloads."""
    return {spec.key for spec in editable_fields()}


def canonical_correction_field_spec(kind: ItemKind, key: str) -> MetadataFieldSpec | None:
    """Return *key* when it is valid for a canonical correction target."""

    spec = field_spec(key)
    if spec is None or not spec.editable or not spec.applies_to(kind):
        return None
    if spec.write_target_for_kind(kind) != "core_canonical":
        return None
    if spec.scope_for_kind(kind) == "internal":
        return None
    return spec


def canonical_correction_target(
    kind: ItemKind,
    keys: Iterable[str],
) -> tuple[str, str] | None:
    """Resolve one canonical scope/entity type for a proposal field set."""

    target: tuple[str, str] | None = None
    for key in keys:
        spec = canonical_correction_field_spec(kind, key)
        if spec is None:
            return None
        current = (
            spec.scope_for_kind(kind),
            spec.source_entity_type_for_kind(kind),
        )
        if target is None:
            target = current
        elif target != current:
            return None
    return target


def canonical_entity_type_for_scope(kind: ItemKind, scope: str) -> str | None:
    """Return the canonical entity type for a structural correction scope."""

    target = CANONICAL_ENTITY_MATRIX.get(kind, {}).get(scope)
    return target[0] if target is not None else None
