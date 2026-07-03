"""Single source of truth for canonical metadata fields.

Historically the catalog metadata fields were declared in many uncoordinated
places: the core normalization lookups (``_KIND_ALLOWED_KEYS``,
``_NORMALIZED_VALUE_TYPES``, ``TYPED_KIND_METADATA_KEYS``), the admin correction
request schema, and the Flutter app's ``kAdminMetadataScalarFields`` contract.
Adding a field meant editing every copy and forgetting one silently broke
ingest/correction (see the ``NormalizedItem.color`` regression).

This module declares each editable field once as a :class:`MetadataFieldSpec`
and derives every lookup from the registry. It is the schema that the admin edit
panel and the Flutter app edit dialog render from (exposed at
``GET /metadata/field-schema``), so the two surfaces can no longer drift apart.

Two concerns are modelled by a single spec:

* **Normalization** — the subset of fields flagged ``normalized=True`` feed the
  ``app.metadata_normalized`` allow-lists / value-type / typed-column lookups.
  These derivations are intentionally scoped so editorial fields can be added
  without changing normalization behaviour.
* **Editing UI** — every ``editable=True`` field is rendered in the edit panel,
  grouped by :attr:`MetadataFieldSpec.section` and rendered with the widget hint
  in :attr:`MetadataFieldSpec.input`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.catalog.grouping_models import PRINT_GROUPING_KINDS
from app.models.base import ItemKind

# Value types understood by normalization/validation + the edit surfaces.
VALUE_TYPE_STRING = "string"
VALUE_TYPE_STRING_LIST = "string_list"
VALUE_TYPE_INTEGER = "integer"
VALUE_TYPE_DATE = "date"
VALUE_TYPE_LINK_LIST = "link_list"

# Edit-panel sections (mirror the app's SharedMetadataEditTab grouping).
SECTION_ITEM = "item"
SECTION_PUBLISHING = "publishing"
SECTION_TECHNICAL = "technical"
SECTION_REGIONAL = "regional"
SECTION_ARTWORK = "artwork"
SECTION_RELATIONS = "relations"
SECTION_INTERNAL = "internal"

# Widget hints for the edit surfaces.
INPUT_TEXT = "text"
INPUT_MULTILINE = "multiline"
INPUT_NUMBER = "number"
INPUT_DATE = "date"
INPUT_LIST = "list"

# Kinds that carry the physical video/disc spec fields.
VIDEO_KINDS: frozenset[ItemKind] = frozenset(
    {ItemKind.anime, ItemKind.movie, ItemKind.tv}
)
# Print kinds (page count, imprint, series group).
PRINT_KINDS: frozenset[ItemKind] = PRINT_GROUPING_KINDS
# Kinds that have trailers (video + interactive).
TRAILER_KINDS: frozenset[ItemKind] = VIDEO_KINDS | frozenset({ItemKind.game})
# Every configured kind (genres applies to all of them).
ALL_KINDS: frozenset[ItemKind] = frozenset(ItemKind)


@dataclass(frozen=True)
class MetadataFieldSpec:
    """One canonical metadata field."""

    key: str
    value_type: str
    label: str
    #: ``True`` for normalized fields shared by every kind (cover/format/audience).
    common: bool = False
    #: ``True`` when the field maps to a typed canonical kind table column.
    typed: bool = False
    #: ``True`` when the field participates in metadata normalization/validation.
    normalized: bool = False
    #: ``True`` when the field is rendered in the user-facing edit panel.
    editable: bool = True
    #: Edit-panel section grouping (one of the ``SECTION_*`` constants).
    section: str = SECTION_ITEM
    #: Edit-panel widget hint (one of the ``INPUT_*`` constants).
    input: str = INPUT_TEXT
    #: Kinds that expose a non-common field. Ignored for common fields.
    kinds: frozenset[ItemKind] = field(default_factory=frozenset)

    def applies_to(self, kind: ItemKind) -> bool:
        return self.common or kind in self.kinds

    def scope_for_kind(self, kind: ItemKind) -> str:
        return _scope_for_kind(kind, self.key)

    def write_target_for_kind(self, kind: ItemKind) -> str:
        return _field_write_target(self.key, kind)

    def source_entity_type_for_kind(self, kind: ItemKind) -> str:
        return _field_source_entity_type(self.key, kind)

    def source_table_for_kind(self, kind: ItemKind) -> str:
        return _field_source_table(self.key, kind)

    @property
    def scope(self) -> str:
        if self.section == SECTION_INTERNAL:
            return "internal"
        if self.common:
            return "common"
        return "kind"

    @property
    def write_target(self) -> str:
        if self.common or self.typed:
            return "kind_specific_table"
        return "canonical_kind_table"

    @property
    def source_entity_type(self) -> str:
        if self.common or self.typed:
            return "kind"
        return "item"

    @property
    def source_table(self) -> str:
        if self.common or self.typed:
            return "kind_specific_table"
        return "items"

    @property
    def is_legacy_projection(self) -> bool:
        return not self.common and not self.typed and self.section != SECTION_INTERNAL


_INTERNAL_BOOKKEEPING_KEYS = {
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

_LEGACY_PROJECTION_KEYS = {
    "cover_image_url",
    "thumbnail_image_url",
    "synopsis",
    "crossover",
    "plot_summary",
    "plot_description",
    "series_tags",
}

_WORK_SCOPE_KEYS = {
    "title",
    "original_title",
    "localized_title",
    "title_extension",
    "sort_key",
    "search_aliases",
    "item_number",
    "genres",
    "platforms",
    "identifiers",
    "company_roles",
    "contributors",
    "mechanics",
    "categories",
    "families",
    "expansions",
    "rankings",
}

_MEDIA_SCOPE_KEYS = {
    "color",
    "nr_discs",
    "screen_ratio",
    "audio_tracks",
    "subtitles",
    "layers",
    "runtime_minutes",
    "track_count",
    "tracks",
}

_TRACK_SCOPE_KEYS = {"tracks"}

_PROPOSAL_KEYS = {"physical_format", "trailer_urls", "external_links"}

_KIND_SCOPE_ENTITY_TYPES: dict[ItemKind, dict[str, tuple[str, str]]] = {
    ItemKind.book: {
        "work": ("book_work", "book_works"),
        "edition": ("book_edition", "book_editions"),
        "media": ("book_edition", "book_editions"),
        "track": ("book_edition", "book_editions"),
    },
    ItemKind.comic: {
        "work": ("comic_work", "comic_works"),
        "edition": ("comic_issue", "comic_issues"),
        "media": ("comic_issue", "comic_issues"),
        "track": ("comic_issue", "comic_issues"),
    },
    ItemKind.manga: {
        "work": ("manga_work", "manga_works"),
        "edition": ("manga_chapter", "manga_chapters"),
        "media": ("manga_chapter", "manga_chapters"),
        "track": ("manga_chapter", "manga_chapters"),
    },
    ItemKind.anime: {
        "work": ("anime_series", "anime_series"),
        "edition": ("anime_series", "anime_series"),
        "episode": ("anime_episode", "anime_episodes"),
        "release": ("anime_series", "anime_series"),
        "media": ("anime_episode", "anime_episodes"),
        "track": ("anime_episode", "anime_episodes"),
    },
    ItemKind.movie: {
        "work": ("movie_work", "movie_works"),
        "release": ("movie_release", "movie_releases"),
        "media": ("movie_release_media", "movie_release_media"),
        "track": ("movie_release_media", "movie_release_media"),
    },
    ItemKind.tv: {
        "work": ("tv_release", "tv_releases"),
        "release": ("tv_release", "tv_releases"),
        "episode": ("tv_episode", "tv_episodes"),
        "media": ("tv_release_media", "tv_release_media"),
        "track": ("tv_release_media", "tv_release_media"),
    },
    ItemKind.game: {
        "work": ("game_work", "game_works"),
        "release": ("game_release", "game_releases"),
        "media": ("game_release", "game_releases"),
        "track": ("game_release", "game_releases"),
    },
    ItemKind.boardgame: {
        "work": ("boardgame_work", "boardgame_works"),
        "edition": ("boardgame_edition", "boardgame_editions"),
        "media": ("boardgame_edition", "boardgame_editions"),
        "track": ("boardgame_edition", "boardgame_editions"),
    },
    ItemKind.music: {
        "release": ("music_release", "music_releases"),
        "media": ("music_media", "music_media"),
        "track": ("music_track", "music_tracks"),
        "work": ("music_release", "music_releases"),
    },
}


def _default_entity_ref(kind: ItemKind) -> tuple[str, str]:
    scope_map = _KIND_SCOPE_ENTITY_TYPES[kind]
    for scope in ("work", "release", "edition", "episode", "media", "track"):
        if scope in scope_map:
            return scope_map[scope]
    return next(iter(scope_map.values()))


def _scope_for_kind(kind: ItemKind, key: str) -> str:
    if key in _INTERNAL_BOOKKEEPING_KEYS:
        return "legacy_projection"
    if key in _LEGACY_PROJECTION_KEYS:
        return "legacy_projection"
    if key == "physical_format":
        if kind in {ItemKind.book, ItemKind.boardgame}:
            return "edition"
        if kind in {ItemKind.comic, ItemKind.manga}:
            return "issue"
        if kind == ItemKind.music:
            return "release"
        return "release"
    if key in _PROPOSAL_KEYS:
        return "legacy_projection"
    if key in _MEDIA_SCOPE_KEYS:
        return "track" if key == "tracks" else "media"
    if key == "edition_title":
        if kind in {ItemKind.comic, ItemKind.manga}:
            return "issue"
        if kind in {ItemKind.book, ItemKind.boardgame}:
            return "edition"
        if kind == ItemKind.music:
            return "release"
        if kind == ItemKind.anime:
            return "episode"
        return "release"
    if key in {"release_date", "publisher", "barcode", "catalog_number", "release_status", "country", "language", "age_rating", "variant_name", "page_count", "imprint", "subtitle", "series_group"}:
        if kind in {ItemKind.book, ItemKind.boardgame}:
            return "edition"
        if kind in {ItemKind.comic, ItemKind.manga}:
            return "issue"
        if kind == ItemKind.anime:
            return "episode"
        if kind == ItemKind.music:
            return "release"
        return "release"
    if key in _WORK_SCOPE_KEYS:
        return "work"
    return "legacy_projection"


def _field_source_entity_type(key: str, kind: ItemKind) -> str:
    scope = _scope_for_kind(kind, key)
    entity_type, _ = _KIND_SCOPE_ENTITY_TYPES[kind].get(scope, _default_entity_ref(kind))
    return entity_type


def _field_source_table(key: str, kind: ItemKind) -> str:
    scope = _scope_for_kind(kind, key)
    _, table_name = _KIND_SCOPE_ENTITY_TYPES[kind].get(scope, _default_entity_ref(kind))
    return table_name


def _field_write_target(key: str, kind: ItemKind) -> str:
    if key in _INTERNAL_BOOKKEEPING_KEYS:
        return "readonly_computed"
    if key in _LEGACY_PROJECTION_KEYS:
        return "legacy_projection"
    if key in _PROPOSAL_KEYS:
        return "core_admin_proposal"
    return "core_canonical"


def contract_rows(kinds: Iterable[ItemKind] | None = None) -> list[dict[str, object]]:
    active_kinds = tuple(kinds or (kind for kind in ItemKind if kind != ItemKind.collection))
    rows: list[dict[str, object]] = []
    for spec in METADATA_FIELDS:
        applicable_kinds = active_kinds if spec.common else tuple(kind for kind in active_kinds if kind in spec.kinds)
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


# --- Normalized common fields (shared by every kind) -------------------------
# Internal cover/format bookkeeping that is never edited by hand.
_INTERNAL_COMMON_FIELDS: tuple[MetadataFieldSpec, ...] = (
    MetadataFieldSpec("physical_format_label", VALUE_TYPE_STRING, "Physical format label",
                      common=True, normalized=True, editable=False, section=SECTION_INTERNAL),
    MetadataFieldSpec("physical_format_media_family", VALUE_TYPE_STRING,
                      "Physical format media family", common=True, normalized=True,
                      editable=False, section=SECTION_INTERNAL),
    MetadataFieldSpec("physical_format_variant_type", VALUE_TYPE_STRING,
                      "Physical format variant type", common=True, normalized=True,
                      editable=False, section=SECTION_INTERNAL),
    MetadataFieldSpec("associated_image_id", VALUE_TYPE_STRING, "Associated image",
                      common=True, normalized=True, editable=False, section=SECTION_INTERNAL),
    MetadataFieldSpec("cover_delivery_url", VALUE_TYPE_STRING, "Cover delivery URL",
                      common=True, normalized=True, editable=False, section=SECTION_INTERNAL),
    MetadataFieldSpec("cover_policy", VALUE_TYPE_STRING, "Cover policy",
                      common=True, normalized=True, editable=False, section=SECTION_INTERNAL),
    MetadataFieldSpec("cover_source_url", VALUE_TYPE_STRING, "Cover source URL",
                      common=True, normalized=True, editable=False, section=SECTION_INTERNAL),
    MetadataFieldSpec("cover_status", VALUE_TYPE_STRING, "Cover status",
                      common=True, normalized=True, editable=False, section=SECTION_INTERNAL),
    MetadataFieldSpec("cover_storage", VALUE_TYPE_STRING, "Cover storage",
                      common=True, normalized=True, editable=False, section=SECTION_INTERNAL),
)

# Editable normalized common fields.
_EDITABLE_COMMON_FIELDS: tuple[MetadataFieldSpec, ...] = (
    MetadataFieldSpec("physical_format", VALUE_TYPE_STRING, "Physical format",
                      common=True, normalized=False, section=SECTION_PUBLISHING),
)

# --- Normalized kind-scoped, typed fields ------------------------------------
_KIND_FIELDS: tuple[MetadataFieldSpec, ...] = (
    MetadataFieldSpec("genres", VALUE_TYPE_STRING_LIST, "Genres", typed=True, normalized=True,
                      section=SECTION_RELATIONS, input=INPUT_LIST, kinds=ALL_KINDS),
    MetadataFieldSpec("platforms", VALUE_TYPE_STRING_LIST, "Platforms", typed=True,
                      normalized=True, section=SECTION_RELATIONS, input=INPUT_LIST,
                      kinds=frozenset({ItemKind.game, ItemKind.boardgame})),
    MetadataFieldSpec("identifiers", VALUE_TYPE_STRING_LIST, "Identifiers",
                      section=SECTION_RELATIONS, input=INPUT_LIST, kinds=frozenset({ItemKind.game, ItemKind.boardgame})),
    MetadataFieldSpec("company_roles", VALUE_TYPE_STRING_LIST, "Company roles",
                      section=SECTION_RELATIONS, input=INPUT_LIST, kinds=frozenset({ItemKind.game})),
    MetadataFieldSpec("contributors", VALUE_TYPE_STRING_LIST, "Contributors",
                      section=SECTION_RELATIONS, input=INPUT_LIST, kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("mechanics", VALUE_TYPE_STRING_LIST, "Mechanics",
                      section=SECTION_RELATIONS, input=INPUT_LIST, kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("categories", VALUE_TYPE_STRING_LIST, "Categories",
                      section=SECTION_RELATIONS, input=INPUT_LIST, kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("families", VALUE_TYPE_STRING_LIST, "Families",
                      section=SECTION_RELATIONS, input=INPUT_LIST, kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("expansions", VALUE_TYPE_STRING_LIST, "Expansions",
                      section=SECTION_RELATIONS, input=INPUT_LIST, kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("rankings", VALUE_TYPE_STRING_LIST, "Rankings",
                      section=SECTION_RELATIONS, input=INPUT_LIST, kinds=frozenset({ItemKind.boardgame})),
    MetadataFieldSpec("color", VALUE_TYPE_STRING, "Color", typed=True, normalized=True,
                      section=SECTION_TECHNICAL, kinds=VIDEO_KINDS),
)

# --- Editorial / release fields (not part of normalization) ------------------
# These are edited by hand on the catalog work + release; they map to canonical
# columns rather than the normalized metadata JSON, so ``normalized=False``.
_EDITORIAL_FIELDS: tuple[MetadataFieldSpec, ...] = (
    # Item identity.
    MetadataFieldSpec("title", VALUE_TYPE_STRING, "Title",
                      section=SECTION_ITEM, kinds=ALL_KINDS),
    MetadataFieldSpec("original_title", VALUE_TYPE_STRING, "Original title",
                      section=SECTION_ITEM, kinds=ALL_KINDS),
    MetadataFieldSpec("localized_title", VALUE_TYPE_STRING, "Localized title",
                      section=SECTION_ITEM, kinds=ALL_KINDS),
    MetadataFieldSpec("title_extension", VALUE_TYPE_STRING, "Title extension",
                      section=SECTION_ITEM, kinds=ALL_KINDS),
    MetadataFieldSpec("sort_key", VALUE_TYPE_STRING, "Sort key",
                      section=SECTION_ITEM, kinds=ALL_KINDS),
    MetadataFieldSpec("search_aliases", VALUE_TYPE_STRING_LIST, "Search aliases",
                      section=SECTION_ITEM, input=INPUT_LIST, kinds=ALL_KINDS),
    MetadataFieldSpec("item_number", VALUE_TYPE_STRING, "Item number",
                      section=SECTION_ITEM, kinds=ALL_KINDS),
    MetadataFieldSpec("edition_title", VALUE_TYPE_STRING, "Edition title",
                      section=SECTION_ITEM, kinds=ALL_KINDS),
    MetadataFieldSpec("release_date", VALUE_TYPE_DATE, "Release date",
                      section=SECTION_ITEM, input=INPUT_DATE, kinds=ALL_KINDS),
    # Publishing.
    MetadataFieldSpec("publisher", VALUE_TYPE_STRING, "Publisher",
                      section=SECTION_PUBLISHING, kinds=ALL_KINDS),
    MetadataFieldSpec("imprint", VALUE_TYPE_STRING, "Imprint",
                      section=SECTION_PUBLISHING, kinds=PRINT_KINDS),
    MetadataFieldSpec("subtitle", VALUE_TYPE_STRING, "Subtitle",
                      section=SECTION_PUBLISHING, kinds=ALL_KINDS),
    MetadataFieldSpec("series_group", VALUE_TYPE_STRING, "Series group",
                      section=SECTION_PUBLISHING, kinds=PRINT_KINDS),
    MetadataFieldSpec("barcode", VALUE_TYPE_STRING, "Barcode",
                      section=SECTION_PUBLISHING, kinds=ALL_KINDS),
    MetadataFieldSpec("variant_name", VALUE_TYPE_STRING, "Primary variant",
                      section=SECTION_PUBLISHING, kinds=ALL_KINDS),
    MetadataFieldSpec("page_count", VALUE_TYPE_INTEGER, "Page count",
                      section=SECTION_PUBLISHING, input=INPUT_NUMBER, kinds=PRINT_KINDS),
    MetadataFieldSpec("runtime_minutes", VALUE_TYPE_INTEGER, "Runtime minutes",
                      section=SECTION_PUBLISHING, input=INPUT_NUMBER, kinds=VIDEO_KINDS),
    # Technical / release.
    MetadataFieldSpec("catalog_number", VALUE_TYPE_STRING, "Catalog number",
                      section=SECTION_TECHNICAL, kinds=ALL_KINDS),
    MetadataFieldSpec("release_status", VALUE_TYPE_STRING, "Release status",
                      section=SECTION_TECHNICAL, kinds=ALL_KINDS),
    MetadataFieldSpec("nr_discs", VALUE_TYPE_INTEGER, "Number of discs",
                      section=SECTION_TECHNICAL, input=INPUT_NUMBER, kinds=VIDEO_KINDS),
    MetadataFieldSpec("screen_ratio", VALUE_TYPE_STRING, "Screen ratio",
                      section=SECTION_TECHNICAL, kinds=VIDEO_KINDS),
    MetadataFieldSpec("audio_tracks", VALUE_TYPE_STRING, "Audio tracks",
                      section=SECTION_TECHNICAL, kinds=VIDEO_KINDS),
    MetadataFieldSpec("subtitles", VALUE_TYPE_STRING, "Subtitles",
                      section=SECTION_TECHNICAL, kinds=VIDEO_KINDS),
    MetadataFieldSpec("layers", VALUE_TYPE_STRING, "Layers",
                      section=SECTION_TECHNICAL, kinds=VIDEO_KINDS),
    # Regional.
    MetadataFieldSpec("country", VALUE_TYPE_STRING, "Country",
                      section=SECTION_REGIONAL, kinds=ALL_KINDS),
    MetadataFieldSpec("language", VALUE_TYPE_STRING, "Language",
                      section=SECTION_REGIONAL, kinds=ALL_KINDS),
    MetadataFieldSpec("age_rating", VALUE_TYPE_STRING, "Age rating",
                      section=SECTION_REGIONAL, kinds=ALL_KINDS),
    MetadataFieldSpec("audience_rating", VALUE_TYPE_STRING, "Audience rating",
                      common=True, typed=True, normalized=True, section=SECTION_REGIONAL),
    MetadataFieldSpec("series_tags", VALUE_TYPE_STRING_LIST, "Series tags",
                      section=SECTION_REGIONAL, input=INPUT_LIST, kinds=ALL_KINDS),
    # Artwork & copy.
    MetadataFieldSpec("cover_image_url", VALUE_TYPE_STRING, "Cover URL",
                      section=SECTION_ARTWORK, kinds=ALL_KINDS),
    MetadataFieldSpec("thumbnail_image_url", VALUE_TYPE_STRING, "Thumbnail URL",
                      section=SECTION_ARTWORK, kinds=ALL_KINDS),
    MetadataFieldSpec("synopsis", VALUE_TYPE_STRING, "Synopsis",
                      section=SECTION_ARTWORK, input=INPUT_MULTILINE, kinds=ALL_KINDS),
    MetadataFieldSpec("crossover", VALUE_TYPE_STRING, "Crossover",
                      section=SECTION_ARTWORK,
                      kinds=frozenset({ItemKind.comic, ItemKind.manga})),
    MetadataFieldSpec("plot_summary", VALUE_TYPE_STRING, "Plot summary",
                      section=SECTION_ARTWORK, input=INPUT_MULTILINE, kinds=ALL_KINDS),
    MetadataFieldSpec("plot_description", VALUE_TYPE_STRING, "Plot description",
                      section=SECTION_ARTWORK, input=INPUT_MULTILINE, kinds=ALL_KINDS),
    # Relations & lists.
    MetadataFieldSpec("trailer_urls", VALUE_TYPE_LINK_LIST, "Trailer URLs",
                      section=SECTION_RELATIONS, input=INPUT_MULTILINE, kinds=TRAILER_KINDS),
    MetadataFieldSpec("external_links", VALUE_TYPE_LINK_LIST, "External links",
                      section=SECTION_RELATIONS, input=INPUT_MULTILINE, kinds=ALL_KINDS),
)

#: The canonical registry, ordered (normalized common first, then kind-scoped,
#: then editorial). Internal bookkeeping fields come first so the normalized
#: derivations keep their historical ordering semantics.
METADATA_FIELDS: tuple[MetadataFieldSpec, ...] = (
    _INTERNAL_COMMON_FIELDS
    + _EDITABLE_COMMON_FIELDS
    + _KIND_FIELDS
    + _EDITORIAL_FIELDS
)

_FIELD_BY_KEY: dict[str, MetadataFieldSpec] = {spec.key: spec for spec in METADATA_FIELDS}


def field_spec(key: str) -> MetadataFieldSpec | None:
    return _FIELD_BY_KEY.get(key)


def common_field_keys() -> set[str]:
    """Normalized common keys (mirrors the legacy ``_COMMON_ALLOWED_KEYS``)."""
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


def editable_fields() -> list[MetadataFieldSpec]:
    """All user-editable specs, in registry order."""
    return [spec for spec in METADATA_FIELDS if spec.editable]
