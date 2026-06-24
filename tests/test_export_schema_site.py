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


def test_catalog_spine_diagram_renders_item_kind_metadata_keys():
    diagrams = _diagrams()
    catalog = next(
        (diagram for domain_id, diagram in diagrams.items() if "ITEM_KIND_METADATA" in diagram),
        None,
    )
    assert catalog is not None, "expected a domain diagram containing ITEM_KIND_METADATA"
    # The exact case that broke rendering: FK + UK on item_id.
    assert "item_id FK, UK" in catalog
    assert "FK UK" not in catalog
    # Subtype tables expose id as both PK and FK.
    assert "id PK, FK" in catalog
    assert "PK FK" not in catalog


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
