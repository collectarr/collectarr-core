"""Golden contract for the unified metadata field registry.

The registry in :mod:`app.catalog.metadata_fields` is the single source of truth
the admin edit panel and the Flutter app edit dialog render from. This snapshot
locks its shape so that any change to a field (key, value type, section, flags or
applicable kinds) is a deliberate, reviewed edit rather than silent drift.
"""

import json

from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS, catalog_kind_for
from app.catalog.metadata_fields import (
    METADATA_FIELDS,
    common_field_keys,
    editable_fields,
    field_spec,
    fields_for_kind,
    kind_allowed_keys,
    normalized_field_spec,
    typed_field_keys,
    value_types,
)
from app.models.base import ItemKind
from scripts.export_contract_bundle import CONTRACT_VERSION, write_contract_bundle

VIDEO = ("movie", "tv")
PRINT = ("book", "comic", "manga")
ALL = tuple(sorted(definition.kind.value for definition in CATALOG_KIND_DEFINITIONS))
NO_MUSIC = tuple(kind for kind in ALL if kind != "music")

# key -> (value_type, normalized, editable, section, sorted kinds) snapshot.
EXPECTED_FIELDS = {'artist': ('string', False, True, 'item', ('music',)),
 'associated_image_id': ('string', True, False, 'internal', ('music',)),
 'audiencerating_templateimage': ('string',
                                  True,
                                  False,
                                  'internal',
                                  ('music',)),
 'audio_templateimage': ('string', True, False, 'internal', ('music',)),
 'barcode': ('string', False, True, 'publishing', ('music',)),
 'box_set': ('string', False, True, 'technical', ('music',)),
 'catalog_number': ('string', False, True, 'technical', ('music',)),
 'country': ('string', False, True, 'regional', ('music',)),
 'country_scaledimage': ('string', True, False, 'internal', ('music',)),
 'cover_delivery_url': ('string', True, False, 'internal', ('music',)),
 'cover_image_url': ('string', False, True, 'artwork', ('music',)),
 'cover_policy': ('string', True, False, 'internal', ('music',)),
 'cover_source_url': ('string', True, False, 'internal', ('music',)),
 'cover_status': ('string', True, False, 'internal', ('music',)),
 'cover_storage': ('string', True, False, 'internal', ('music',)),
 'external_links': ('link_list', False, True, 'relations', ('music',)),
 'extra': ('string_list', False, True, 'technical', ('music',)),
 'format_scaledimage': ('string', True, False, 'internal', ('music',)),
 'format_templateimage': ('string', True, False, 'internal', ('music',)),
 'genres': ('string_list', True, True, 'relations', ('music',)),
 'label': ('string', False, True, 'publishing', ('music',)),
 'language_scaledimage': ('string', True, False, 'internal', ('music',)),
 'original_release_date': ('partial_date', False, True, 'item', ('music',)),
 'packaging': ('string', False, True, 'publishing', ('music',)),
 'physical_format_label': ('string', True, False, 'internal', ('music',)),
 'physical_format_media_family': ('string',
                                  True,
                                  False,
                                  'internal',
                                  ('music',)),
 'physical_format_variant_type': ('string',
                                  True,
                                  False,
                                  'internal',
                                  ('music',)),
 'region_scaledimage': ('string', True, False, 'internal', ('music',)),
 'release_date': ('partial_date', False, True, 'item', ('music',)),
 'sort_title': ('string', False, True, 'item', ('music',)),
 'subtitle': ('string', False, True, 'publishing', ('music',)),
 'thumbnail_image_url': ('string', False, True, 'artwork', ('music',)),
 'title': ('string', False, True, 'item', ('music',))}

def test_metadata_field_registry_matches_golden_contract():
    actual = {
        spec.key: (
            spec.value_type,
            (
                normalized_field_spec(spec.key) is not None
                and spec.kinds.issubset(normalized_field_spec(spec.key).kinds)
            ),
            spec.editable,
            spec.section,
            tuple(sorted(k.value for k in spec.kinds if k is ItemKind.music)),
        )
        for spec in METADATA_FIELDS
        if not spec.correction_only and spec.applies_to(ItemKind.music)
    }
    assert actual == EXPECTED_FIELDS


def test_music_nested_fields_are_only_exposed_to_canonical_corrections():
    nested_fields = {"artist_credits", "credits", "discs"}
    registered = fields_for_kind(
        ItemKind.music, editable_only=True, include_correction_only=True
    )
    assert nested_fields <= {field.key for field in registered}
    assert nested_fields.isdisjoint(
        field.key for field in fields_for_kind(ItemKind.music, editable_only=True)
    )
    assert nested_fields.isdisjoint(field.key for field in editable_fields())
    assert all(
        field.correction_only for field in registered if field.key in nested_fields
    )


def test_normalized_derivations_are_byte_for_byte_stable():
    """The normalization lookups must not change when editorial fields are added."""
    assert common_field_keys() == {
        "associated_image_id",
        "audiencerating_templateimage",
        "audio_templateimage",
        "country_scaledimage",
        "cover_delivery_url",
        "cover_policy",
        "cover_source_url",
        "cover_status",
        "cover_storage",
        "format_scaledimage",
        "format_templateimage",
        "language_scaledimage",
        "physical_format_label",
        "physical_format_media_family",
        "physical_format_variant_type",
        "region_scaledimage",
    }
    assert typed_field_keys() == {
        "genres",
    }
    vt = value_types()
    assert vt["genres"] == "string_list"
    assert "nr_discs" not in vt
    # Editorial fields must NOT leak into the normalized value-type map.
    assert "title" not in vt
    assert "synopsis" not in vt
    allowed = kind_allowed_keys()
    assert allowed[ItemKind.music] == {"genres"}
    assert set(allowed) == {ItemKind.music, ItemKind.game, ItemKind.game_hardware, ItemKind.game_toy}


def test_editable_fields_exclude_internal_bookkeeping():
    editable_keys = {spec.key for spec in editable_fields()}
    assert "cover_storage" not in editable_keys
    assert "associated_image_id" not in editable_keys
    assert "title" in editable_keys
    assert "genres" in editable_keys


def test_fields_for_kind_is_common_plus_kind_scoped():
    for kind in (ItemKind.music,):
        keys = [spec.key for spec in fields_for_kind(kind)]
        assert len(keys) == len(set(keys))
        for key in EXPECTED_FIELDS:
            spec = next(s for s in METADATA_FIELDS if s.key == key)
            should_apply = kind in spec.kinds
            assert (key in keys) is should_apply


def test_kind_definitions_own_root_models_documents_and_route_metadata():
    assert len(CATALOG_KIND_DEFINITIONS) == 4
    for definition in CATALOG_KIND_DEFINITIONS:
        assert definition.model.__tablename__
        assert definition.document is not None
        assert definition.entity_type.startswith("catalog_")
        assert catalog_kind_for(definition.kind) is definition

    assert field_spec("artist", ItemKind.music) is not None
    assert field_spec("runtime_minutes", ItemKind.movie) is None
    assert field_spec("runtime_minutes", ItemKind.game) is None


def test_contract_bundle_metadata_field_schema_contract(tmp_path):
    write_contract_bundle(tmp_path)
    field_schema = json.loads((tmp_path / "metadata-field-schema.json").read_text(encoding="utf-8"))

    assert field_schema["contractVersion"] == CONTRACT_VERSION
    assert field_schema["fields"]

    for row in field_schema["fields"]:
        assert {"key", "kind", "valueType", "label", "section", "input", "editable"} <= row.keys()
        assert not {
            "scope",
            "writeTarget",
            "sourceEntityType",
            "sourceTable",
            "normalized",
            "typed",
            "common",
        }.intersection(row)


def test_exported_field_schema_only_describes_fields_and_applicability(tmp_path):
    write_contract_bundle(tmp_path)
    field_schema = json.loads((tmp_path / "metadata-field-schema.json").read_text(encoding="utf-8"))
    active_kinds = {definition.kind.value for definition in CATALOG_KIND_DEFINITIONS}
    assert {row["kind"] for row in field_schema["fields"]} <= active_kinds
    assert all(
        row["key"] in {spec.key for spec in METADATA_FIELDS} for row in field_schema["fields"]
    )
