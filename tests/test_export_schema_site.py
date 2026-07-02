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

from scripts.export_schema_site import build_schema_data

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


def test_catalog_spine_diagram_renders_only_the_shared_item_kind_metadata_base():
    diagrams = _diagrams()
    catalog = diagrams["catalog"]
    assert "ITEM_KIND_METADATA {" in catalog
    # The exact case that broke rendering: FK + UK on item_id.
    assert "item_id FK, UK" in catalog
    assert "FK UK" not in catalog
    assert "ITEM_KIND_METADATA_ANIME" not in catalog
    assert "ITEM_KIND_METADATA_MUSIC" not in catalog


def test_kind_views_do_not_surface_item_kind_metadata_subtypes():
    data = build_schema_data()
    kinds = {kind["id"]: kind for kind in data["kinds"]}

    assert "ITEM_KIND_METADATA_ANIME" not in kinds["anime"]["diagram"]
    assert "ITEM_KIND_METADATA_COMIC" not in kinds["comic"]["diagram"]
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


def test_kind_views_surface_v1_work_tables():
    data = build_schema_data()
    kinds = {kind["id"]: kind for kind in data["kinds"]}
    misc_tables = next(domain["tables"] for domain in data["domains"] if domain["id"] == "misc")

    assert "comic_works" in kinds["comic"]["tables"]
    assert "comic_volumes" in kinds["comic"]["tables"]
    assert "book_works" in kinds["book"]["tables"]
    assert "book_series" in kinds["book"]["tables"]
    assert "music_releases" in kinds["music"]["tables"]
    assert "tv_releases" in kinds["tv"]["tables"]

    assert "comic_works" not in misc_tables
    assert "book_works" not in misc_tables
    assert "music_releases" not in misc_tables
    assert "tv_releases" not in misc_tables


def test_legacy_generic_tables_are_omitted_from_the_interactive_view():
    data = build_schema_data()
    table_names = {table["name"] for table in data["tables"]}
    assert "items" not in table_names
    assert "editions" not in table_names
    assert "variants" not in table_names


def test_catalog_spine_marks_bundle_bridge_tables_as_legacy():
    data = build_schema_data()
    catalog = next(domain for domain in data["domains"] if domain["id"] == "catalog")

    assert catalog["title"] == "Catalog Spine (Legacy / Projection)"
    assert "legacy compatibility tables" in catalog["description"].lower()
    assert "bundle bridge tables" in catalog["description"].lower()
    assert "bundle_releases" in catalog["tables"]
    assert "bundle_release_components" in catalog["tables"]
    assert "bundle_release_items" not in catalog["tables"]
