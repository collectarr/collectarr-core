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

VIDEO = ("anime", "movie", "tv")
PRINT = ("book", "comic", "manga")
ALL = tuple(sorted(definition.kind.value for definition in CATALOG_KIND_DEFINITIONS))
NO_MUSIC = tuple(kind for kind in ALL if kind != "music")

# key -> (value_type, normalized, editable, section, sorted kinds) snapshot.
EXPECTED_FIELDS: dict[str, tuple[str, bool, bool, str, tuple[str, ...]]] = {'age_rating': ('string',
                False,
                True,
                'regional',
                ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'artist': ('string', False, True, 'item', ('music',)),
 'artists': ('string_list', False, True, 'relations', ('boardgame',)),
 'associated_image_id': ('string',
                         True,
                         False,
                         'internal',
                         ('anime',
                          'boardgame',
                          'book',
                          'comic',
                          'game',
                          'manga',
                          'movie',
                          'music',
                          'tv')),
 'audience_rating': ('string',
                     True,
                     True,
                     'regional',
                     ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'audiencerating_templateimage': ('string',
                                  True,
                                  False,
                                  'internal',
                                  ('anime',
                                   'boardgame',
                                   'book',
                                   'comic',
                                   'game',
                                   'manga',
                                   'movie',
                                   'music',
                                   'tv')),
 'audio_length_minutes': ('integer', False, True, 'technical', ('book',)),
 'audio_templateimage': ('string',
                         True,
                         False,
                         'internal',
                         ('anime',
                          'boardgame',
                          'book',
                          'comic',
                          'game',
                          'manga',
                          'movie',
                          'music',
                          'tv')),
 'audio_tracks': ('string', False, True, 'technical', ('anime', 'movie', 'tv')),
 'back_cover_image_url': ('string', False, True, 'artwork', ('book',)),
 'barcode': ('string',
             False,
             True,
             'publishing',
             ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'music', 'tv')),
 'best_players': ('string', False, True, 'item', ('boardgame',)),
 'bgg_rank': ('integer', False, True, 'item', ('boardgame',)),
 'bgg_rating': ('number', False, True, 'item', ('boardgame',)),
 'bgg_rating_count': ('integer', False, True, 'item', ('boardgame',)),
 'binding': ('string', False, True, 'publishing', ('book',)),
 'box_set': ('string', False, True, 'technical', ('music',)),
 'catalog_number': ('string',
                    False,
                    True,
                    'technical',
                    ('anime',
                     'boardgame',
                     'book',
                     'comic',
                     'game',
                     'manga',
                     'movie',
                     'music',
                     'tv')),
 'categories': ('string_list', False, True, 'relations', ('boardgame',)),
 'characters': ('string_list', False, True, 'relations', ('boardgame',)),
 'color': ('string', True, True, 'technical', ('anime', 'movie', 'tv')),
 'company_roles': ('string_list', False, True, 'relations', ('game',)),
 'complexity_weight': ('number', False, True, 'item', ('boardgame',)),
 'contributors': ('string_list', False, True, 'relations', ('boardgame',)),
 'country': ('string',
             False,
             True,
             'regional',
             ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'music', 'tv')),
 'country_scaledimage': ('string',
                         True,
                         False,
                         'internal',
                         ('anime',
                          'boardgame',
                          'book',
                          'comic',
                          'game',
                          'manga',
                          'movie',
                          'music',
                          'tv')),
 'cover_delivery_url': ('string',
                        True,
                        False,
                        'internal',
                        ('anime',
                         'boardgame',
                         'book',
                         'comic',
                         'game',
                         'manga',
                         'movie',
                         'music',
                         'tv')),
 'cover_image_url': ('string',
                     False,
                     True,
                     'artwork',
                     ('anime',
                      'boardgame',
                      'book',
                      'comic',
                      'game',
                      'manga',
                      'movie',
                      'music',
                      'tv')),
 'cover_policy': ('string',
                  True,
                  False,
                  'internal',
                  ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'music', 'tv')),
 'cover_source_url': ('string',
                      True,
                      False,
                      'internal',
                      ('anime',
                       'boardgame',
                       'book',
                       'comic',
                       'game',
                       'manga',
                       'movie',
                       'music',
                       'tv')),
 'cover_status': ('string',
                  True,
                  False,
                  'internal',
                  ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'music', 'tv')),
 'cover_storage': ('string',
                   True,
                   False,
                   'internal',
                   ('anime',
                    'boardgame',
                    'book',
                    'comic',
                    'game',
                    'manga',
                    'movie',
                    'music',
                    'tv')),
 'crossover': ('string', False, True, 'artwork', ('comic', 'manga')),
 'designers': ('string_list', False, True, 'relations', ('boardgame',)),
 'dimensions': ('string', False, True, 'technical', ('book',)),
 'display_title': ('string', False, True, 'item', ('movie',)),
 'distributor': ('string', False, True, 'publishing', ('book',)),
 'edition_statement': ('string', False, True, 'publishing', ('book',)),
 'edition_title': ('string',
                   False,
                   True,
                   'item',
                   ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'expansion_for': ('string', False, True, 'relations', ('boardgame',)),
 'expansions': ('string_list', False, True, 'relations', ('boardgame',)),
 'external_links': ('link_list',
                    False,
                    True,
                    'relations',
                    ('anime',
                     'boardgame',
                     'book',
                     'comic',
                     'game',
                     'manga',
                     'movie',
                     'music',
                     'tv')),
 'extra': ('string_list', False, True, 'technical', ('music',)),
 'families': ('string_list', False, True, 'relations', ('boardgame',)),
 'first_edition': ('boolean', False, True, 'item', ('book',)),
 'first_publication_date': ('partial_date', False, True, 'publishing', ('book',)),
 'format_scaledimage': ('string',
                        True,
                        False,
                        'internal',
                        ('anime',
                         'boardgame',
                         'book',
                         'comic',
                         'game',
                         'manga',
                         'movie',
                         'music',
                         'tv')),
 'format_templateimage': ('string',
                          True,
                          False,
                          'internal',
                          ('anime',
                           'boardgame',
                           'book',
                           'comic',
                           'game',
                           'manga',
                           'movie',
                           'music',
                           'tv')),
 'franchise': ('string', False, True, 'relations', ('game',)),
 'genres': ('string_list',
            True,
            True,
            'relations',
            ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'music', 'tv')),
 'identifiers': ('string_list', False, True, 'relations', ('boardgame', 'game')),
 'imprint': ('string', False, True, 'publishing', ('book', 'comic', 'manga')),
 'item_number': ('string',
                 False,
                 True,
                 'item',
                 ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'label': ('string', False, True, 'publishing', ('music',)),
 'language': ('string',
              False,
              True,
              'regional',
              ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'language_scaledimage': ('string',
                          True,
                          False,
                          'internal',
                          ('anime',
                           'boardgame',
                           'book',
                           'comic',
                           'game',
                           'manga',
                           'movie',
                           'music',
                           'tv')),
 'languages': ('string_list', False, True, 'regional', ('boardgame', 'game')),
 'layers': ('string', False, True, 'technical', ('anime', 'movie', 'tv')),
 'localized_title': ('string',
                     False,
                     True,
                     'item',
                     ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'max_playtime_minutes': ('integer', False, True, 'item', ('boardgame',)),
 'mechanics': ('string_list', False, True, 'relations', ('boardgame',)),
 'min_playtime_minutes': ('integer', False, True, 'item', ('boardgame',)),
 'nr_discs': ('integer', False, True, 'technical', ('anime', 'movie', 'tv')),
 'original_language': ('string', False, True, 'regional', ('boardgame', 'book', 'game', 'movie')),
 'original_publication_date': ('partial_date', False, True, 'publishing', ('book',)),
 'original_release_date': ('partial_date', False, True, 'item', ('music',)),
 'original_title': ('string',
                    False,
                    True,
                    'item',
                    ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'packaging': ('string', False, True, 'publishing', ('music',)),
 'page_count': ('integer', False, True, 'publishing', ('book', 'comic', 'manga')),
 'physical_format': ('string',
                     False,
                     True,
                     'publishing',
                     ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'physical_format_label': ('string',
                           True,
                           False,
                           'internal',
                           ('anime',
                            'boardgame',
                            'book',
                            'comic',
                            'game',
                            'manga',
                            'movie',
                            'music',
                            'tv')),
 'physical_format_media_family': ('string',
                                  True,
                                  False,
                                  'internal',
                                  ('anime',
                                   'boardgame',
                                   'book',
                                   'comic',
                                   'game',
                                   'manga',
                                   'movie',
                                   'music',
                                   'tv')),
 'physical_format_variant_type': ('string',
                                  True,
                                  False,
                                  'internal',
                                  ('anime',
                                   'boardgame',
                                   'book',
                                   'comic',
                                   'game',
                                   'manga',
                                   'movie',
                                   'music',
                                   'tv')),
 'platforms': ('string_list', True, True, 'relations', ('boardgame', 'game')),
 'plot_description': ('string',
                      False,
                      True,
                      'artwork',
                      ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'plot_summary': ('string',
                  False,
                  True,
                  'artwork',
                  ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'production_companies': ('string_list', False, True, 'publishing', ('movie',)),
 'publisher': ('string',
               False,
               True,
               'publishing',
               ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'publishers': ('string_list', False, True, 'publishing', ('boardgame',)),
 'rankings': ('string_list', False, True, 'relations', ('boardgame',)),
 'recommended_players': ('string', False, True, 'item', ('boardgame',)),
 'region': ('string', False, True, 'regional', ('book',)),
 'region_scaledimage': ('string',
                        True,
                        False,
                        'internal',
                        ('anime',
                         'boardgame',
                         'book',
                         'comic',
                         'game',
                         'manga',
                         'movie',
                         'music',
                         'tv')),
 'release_date': ('partial_date',
                  False,
                  True,
                  'item',
                  ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'music', 'tv')),
 'release_status': ('string',
                    False,
                    True,
                    'technical',
                    ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'runtime_minutes': ('integer', False, True, 'publishing', ('anime', 'movie', 'tv')),
 'screen_ratio': ('string', False, True, 'technical', ('anime', 'movie', 'tv')),
 'search_aliases': ('string_list',
                    False,
                    True,
                    'item',
                    ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'series_group': ('string', False, True, 'publishing', ('book', 'comic', 'manga')),
 'series_tags': ('string_list',
                 False,
                 True,
                 'regional',
                 ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'series_title': ('string',
                  False,
                  True,
                  'item',
                  ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'sort_key': ('string',
              False,
              True,
              'item',
              ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'sort_title': ('string', False, True, 'item', ('music',)),
 'studio': ('string', False, True, 'publishing', ('movie',)),
 'subjects': ('string_list', False, True, 'relations', ('book',)),
 'subtitle': ('string',
              False,
              True,
              'publishing',
              ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'music', 'tv')),
 'subtitles': ('string', False, True, 'technical', ('anime', 'movie', 'tv')),
 'synopsis': ('string',
              False,
              True,
              'artwork',
              ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'themes': ('string_list', False, True, 'relations', ('boardgame',)),
 'thumbnail_image_url': ('string',
                         False,
                         True,
                         'artwork',
                         ('anime',
                          'boardgame',
                          'book',
                          'comic',
                          'game',
                          'manga',
                          'movie',
                          'music',
                          'tv')),
 'title': ('string',
           False,
           True,
           'item',
           ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'music', 'tv')),
 'title_extension': ('string',
                     False,
                     True,
                     'item',
                     ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv')),
 'toy_subtype': ('string', False, True, 'item', ('game',)),
 'toy_type': ('string', False, True, 'item', ('game',)),
 'trailer_urls': ('link_list', False, True, 'relations', ('anime', 'game', 'movie', 'tv')),
 'variant_name': ('string',
                  False,
                  True,
                  'publishing',
                  ('anime', 'boardgame', 'book', 'comic', 'game', 'manga', 'movie', 'tv'))}

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
            tuple(sorted(k.value for k in spec.kinds)),
        )
        for spec in METADATA_FIELDS
        if not spec.correction_only
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
        "audience_rating",
        "genres",
        "platforms",
        "color",
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
            should_apply = kind in spec.kinds
            assert (key in keys) is should_apply


def test_kind_definitions_own_root_models_documents_and_route_metadata():
    assert len(CATALOG_KIND_DEFINITIONS) == 9
    for definition in CATALOG_KIND_DEFINITIONS:
        assert definition.model.__tablename__
        assert definition.document is not None
        assert definition.entity_type.startswith("catalog_")
        assert catalog_kind_for(definition.kind) is definition

    assert field_spec("age_rating", ItemKind.game) is not None
    assert field_spec("runtime_minutes", ItemKind.movie) is not None
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
