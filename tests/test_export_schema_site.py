"""Regression tests for the schema-site Mermaid ER diagram generator.

These guard the two failure modes that previously produced an empty / unparseable
"catalog spine" diagram:

* multiple key constraints on one attribute must be comma-separated
  (``FK, UK`` / ``PK, FK``), not space-separated (``FK UK``), or Mermaid raises
  ``Expecting 'ATTRIBUTE_WORD' ... got 'ATTRIBUTE_KEY'``;
* multiple foreign keys between the same entity pair must be merged into a single
  relationship line (parallel edges break Mermaid's dagre ER layout).
"""

import re

from app.db.schema_migrations import RELEASE_TABLE_NAMES
from scripts.export_schema_site import HIDDEN_TABLE_NAMES, build_schema_data

_ATTR_LINE = re.compile(r"^\s{4}\S+\s+\w+(?P<keys>(?:\s+(?:PK|FK|UK)\b,?)*)\s*$")


def _diagrams() -> dict[str, str]:
    data = build_schema_data()
    return {domain["id"]: domain["diagram"] for domain in data["domains"]}


def test_multiple_attribute_keys_are_comma_separated():
    for domain_id, diagram in _diagrams().items():
        for line in diagram.splitlines():
            # Only inspect attribute lines that carry >=2 key constraints.
            tokens = line.strip().split()
            keys = [tok.rstrip(",") for tok in tokens if tok.rstrip(",") in {"PK", "FK", "UK"}]
            if len(keys) < 2:
                continue
            # Every key except the last must be comma-terminated.
            key_tokens = [tok for tok in tokens if tok.rstrip(",") in {"PK", "FK", "UK"}]
            for tok in key_tokens[:-1]:
                assert tok.endswith(","), (
                    f"{domain_id}: multiple keys must be comma-separated, got {line!r}"
                )


def test_catalog_spine_diagram_hides_deprecated_kind_metadata():
    diagrams = _diagrams()
    catalog = diagrams["catalog"]
    assert "ITEM_KIND_METADATA {" not in catalog
    assert "ITEM_KIND_METADATA_TAXONOMIES {" not in catalog
    assert "items {" not in catalog
    assert "editions {" not in catalog
    assert "variants {" not in catalog


def test_kind_views_do_not_surface_kind_metadata_subtypes():
    data = build_schema_data()
    kinds = {kind["id"]: kind for kind in data["kinds"]}

    assert set(kinds) == {"music"}
    assert "ITEM_KIND_METADATA_MUSIC" not in kinds["music"]["diagram"]


def test_no_parallel_edges_between_same_entity_pair():
    for domain_id, diagram in _diagrams().items():
        pair_counts: dict[tuple[str, str], int] = {}
        for line in diagram.splitlines():
            match = re.match(r"\s*(\w+)\s+[|o}{<>.-]+\s+(\w+)\s*:", line)
            if not match:
                continue
            pair = (match.group(1), match.group(2))
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
        duplicates = {pair: count for pair, count in pair_counts.items() if count > 1}
        assert not duplicates, f"{domain_id}: parallel edges must be merged: {duplicates}"


def test_kind_views_surface_only_the_released_music_catalog():
    data = build_schema_data()
    kinds = {kind["id"]: kind for kind in data["kinds"]}
    assert set(kinds) == {"music"}
    assert "music_items" in kinds["music"]["tables"]
    assert not {"book_items", "comic_items", "tv_items", "music_item_discs", "music_item_tracks"}.intersection(kinds["music"]["tables"])


def test_schema_view_contains_only_declared_tables():
    data = build_schema_data()
    table_names = {table["name"] for table in data["tables"]}
    assert table_names == (RELEASE_TABLE_NAMES | {"schema_migrations"}) - HIDDEN_TABLE_NAMES
    assert {
        "game_works",
        "game_releases",
        "boardgame_works",
        "boardgame_editions",
    }.isdisjoint(table_names)


def test_catalog_spine_describes_the_released_music_table():
    data = build_schema_data()
    catalog = next(domain for domain in data["domains"] if domain["id"] == "catalog")
    assert catalog["title"] == "Catalog Spine"
    assert catalog["tables"] == ["music_items"]
