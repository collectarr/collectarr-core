"""Golden contract for the unified metadata field registry.

The registry in :mod:`app.catalog.metadata_fields` is the single source of truth
the admin edit panel and the Flutter app edit dialog render from. This snapshot
locks its shape so that any change to a field (key, value type, common/typed flag
or applicable kinds) is a deliberate, reviewed edit rather than silent drift.
"""

from app.catalog.metadata_fields import (
    METADATA_FIELDS,
    fields_for_kind,
)
from app.models.base import ItemKind

# (key, value_type, common, typed, sorted kinds) — order-independent snapshot.
EXPECTED_FIELDS: dict[str, tuple[str, bool, bool, tuple[str, ...]]] = {
    "audience_rating": ("string", True, True, ()),
    "physical_format": ("string", True, False, ()),
    "physical_format_label": ("string", True, False, ()),
    "physical_format_media_family": ("string", True, False, ()),
    "physical_format_variant_type": ("string", True, False, ()),
    "associated_image_id": ("string", True, False, ()),
    "cover_delivery_url": ("string", True, False, ()),
    "cover_policy": ("string", True, False, ()),
    "cover_source_url": ("string", True, False, ()),
    "cover_status": ("string", True, False, ()),
    "cover_storage": ("string", True, False, ()),
    "genres": (
        "string_list",
        False,
        True,
        tuple(sorted(k.value for k in ItemKind)),
    ),
    "platforms": ("string_list", False, True, ("boardgame", "game")),
    "track_count": ("integer", False, True, ("music",)),
    "tracks": ("track_list", False, True, ("music",)),
    "color": ("string", False, True, ("anime", "bluray", "movie", "tv")),
    "nr_discs": ("integer", False, True, ("anime", "bluray", "movie", "tv")),
    "screen_ratio": ("string", False, True, ("anime", "bluray", "movie", "tv")),
    "audio_tracks": ("string", False, True, ("anime", "bluray", "movie", "tv")),
    "subtitles": ("string", False, True, ("anime", "bluray", "movie", "tv")),
    "layers": ("string", False, True, ("anime", "bluray", "movie", "tv")),
}


def test_metadata_field_registry_matches_golden_contract():
    actual = {
        spec.key: (
            spec.value_type,
            spec.common,
            spec.typed,
            tuple(sorted(k.value for k in spec.kinds)),
        )
        for spec in METADATA_FIELDS
    }
    assert actual == EXPECTED_FIELDS


def test_fields_for_kind_is_common_plus_kind_scoped():
    for kind in ItemKind:
        keys = [spec.key for spec in fields_for_kind(kind)]
        # No duplicates and every common field is present for every kind.
        assert len(keys) == len(set(keys))
        for key, (_vt, common, _typed, kinds) in EXPECTED_FIELDS.items():
            should_apply = common or kind.value in kinds
            assert (key in keys) is should_apply
