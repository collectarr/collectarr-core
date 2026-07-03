"""Golden contract for the unified metadata field registry.

The registry in :mod:`app.catalog.metadata_fields` is the single source of truth
the admin edit panel and the Flutter app edit dialog render from. This snapshot
locks its shape so that any change to a field (key, value type, section, flags or
applicable kinds) is a deliberate, reviewed edit rather than silent drift.
"""

from app.catalog.metadata_fields import (
    METADATA_FIELDS,
    common_field_keys,
    editable_fields,
    fields_for_kind,
    kind_allowed_keys,
    typed_field_keys,
    value_types,
)
from app.models.base import ItemKind

VIDEO = ("anime", "movie", "tv")
PRINT = ("book", "comic", "manga")
ALL = tuple(sorted(k.value for k in ItemKind))

# key -> (value_type, normalized, editable, section, sorted kinds) snapshot.
EXPECTED_FIELDS: dict[str, tuple[str, bool, bool, str, tuple[str, ...]]] = {
    # Internal normalized bookkeeping (not editable).
    "physical_format_label": ("string", True, False, "internal", ()),
    "physical_format_media_family": ("string", True, False, "internal", ()),
    "physical_format_variant_type": ("string", True, False, "internal", ()),
    "associated_image_id": ("string", True, False, "internal", ()),
    "cover_delivery_url": ("string", True, False, "internal", ()),
    "cover_policy": ("string", True, False, "internal", ()),
    "cover_source_url": ("string", True, False, "internal", ()),
    "cover_status": ("string", True, False, "internal", ()),
    "cover_storage": ("string", True, False, "internal", ()),
    # Editable normalized common.
    "audience_rating": ("string", True, True, "regional", ()),
    "physical_format": ("string", False, True, "publishing", ()),
    # Editable normalized kind-scoped.
    "genres": ("string_list", True, True, "relations", ALL),
    "platforms": ("string_list", True, True, "relations", ("boardgame", "game")),
    "color": ("string", True, True, "technical", VIDEO),
    "nr_discs": ("integer", False, True, "technical", VIDEO),
    "screen_ratio": ("string", False, True, "technical", VIDEO),
    "audio_tracks": ("string", False, True, "technical", VIDEO),
    "subtitles": ("string", False, True, "technical", VIDEO),
    "layers": ("string", False, True, "technical", VIDEO),
    # Editorial (not normalized).
    "title": ("string", False, True, "item", ALL),
    "original_title": ("string", False, True, "item", ALL),
    "localized_title": ("string", False, True, "item", ALL),
    "title_extension": ("string", False, True, "item", ALL),
    "sort_key": ("string", False, True, "item", ALL),
    "search_aliases": ("string_list", False, True, "item", ALL),
    "item_number": ("string", False, True, "item", ALL),
    "edition_title": ("string", False, True, "item", ALL),
    "release_date": ("date", False, True, "item", ALL),
    "publisher": ("string", False, True, "publishing", ALL),
    "imprint": ("string", False, True, "publishing", PRINT),
    "subtitle": ("string", False, True, "publishing", ALL),
    "series_group": ("string", False, True, "publishing", PRINT),
    "barcode": ("string", False, True, "publishing", ALL),
    "variant_name": ("string", False, True, "publishing", ALL),
    "page_count": ("integer", False, True, "publishing", PRINT),
    "runtime_minutes": ("integer", False, True, "publishing", VIDEO),
    "catalog_number": ("string", False, True, "technical", ALL),
    "release_status": ("string", False, True, "technical", ALL),
    "country": ("string", False, True, "regional", ALL),
    "language": ("string", False, True, "regional", ALL),
    "age_rating": ("string", False, True, "regional", ALL),
    "series_tags": ("string_list", False, True, "regional", ALL),
    "cover_image_url": ("string", False, True, "artwork", ALL),
    "thumbnail_image_url": ("string", False, True, "artwork", ALL),
    "synopsis": ("string", False, True, "artwork", ALL),
    "crossover": ("string", False, True, "artwork", ("comic", "manga")),
    "plot_summary": ("string", False, True, "artwork", ALL),
    "plot_description": ("string", False, True, "artwork", ALL),
    "trailer_urls": (
        "link_list", False, True, "relations",
        ("anime", "game", "movie", "tv"),
    ),
    "external_links": ("link_list", False, True, "relations", ALL),
}


def test_metadata_field_registry_matches_golden_contract():
    actual = {
        spec.key: (
            spec.value_type,
            spec.normalized,
            spec.editable,
            spec.section,
            tuple(sorted(k.value for k in spec.kinds)),
        )
        for spec in METADATA_FIELDS
    }
    assert actual == EXPECTED_FIELDS


def test_normalized_derivations_are_byte_for_byte_stable():
    """The normalization lookups must not change when editorial fields are added."""
    assert common_field_keys() == {
        "associated_image_id", "audience_rating", "cover_delivery_url", "cover_policy",
        "cover_source_url", "cover_status", "cover_storage", "physical_format_label", "physical_format_media_family",
        "physical_format_variant_type",
    }
    assert typed_field_keys() == {
        "audience_rating", "genres", "platforms", "color",
    }
    vt = value_types()
    assert vt["genres"] == "string_list"
    assert "nr_discs" not in vt
    # Editorial fields must NOT leak into the normalized value-type map.
    assert "title" not in vt
    assert "synopsis" not in vt
    allowed = kind_allowed_keys()
    assert allowed[ItemKind.music] == {"genres"}
    assert "title" not in allowed[ItemKind.comic]


def test_editable_fields_exclude_internal_bookkeeping():
    editable_keys = {spec.key for spec in editable_fields()}
    assert "cover_storage" not in editable_keys
    assert "associated_image_id" not in editable_keys
    assert "title" in editable_keys
    assert "genres" in editable_keys


def test_fields_for_kind_is_common_plus_kind_scoped():
    for kind in ItemKind:
        keys = [spec.key for spec in fields_for_kind(kind)]
        assert len(keys) == len(set(keys))
        for key in EXPECTED_FIELDS:
            spec = next(s for s in METADATA_FIELDS if s.key == key)
            should_apply = spec.common or kind in spec.kinds
            assert (key in keys) is should_apply
