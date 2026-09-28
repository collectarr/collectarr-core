"""Regression checks for the Catalog Item v1 schema documentation exporter."""

import re

from app.models.base import Base
from scripts.export_schema_site import HIDDEN_TABLE_NAMES, build_schema_data


def _diagrams() -> dict[str, str]:
    data = build_schema_data()
    return {domain["id"]: domain["diagram"] for domain in data["domains"]}


def test_multiple_attribute_keys_are_comma_separated():
    for domain_id, diagram in _diagrams().items():
        for line in diagram.splitlines():
            tokens = line.strip().split()
            key_tokens = [token for token in tokens if token.rstrip(",") in {"PK", "FK", "UK"}]
            if len(key_tokens) < 2:
                continue
            for token in key_tokens[:-1]:
                assert token.endswith(","), f"{domain_id}: invalid key formatting in {line!r}"


def test_repeated_foreign_key_pairs_do_not_create_parallel_edges():
    for domain_id, diagram in _diagrams().items():
        pair_counts: dict[tuple[str, str], int] = {}
        for line in diagram.splitlines():
            match = re.match(r"\s*(\w+)\s+[|o}{<>.-]+\s+(\w+)\s*:", line)
            if match:
                pair = (match.group(1), match.group(2))
                pair_counts[pair] = pair_counts.get(pair, 0) + 1
        assert not {pair: count for pair, count in pair_counts.items() if count > 1}, domain_id


def test_every_kind_uses_the_shared_catalog_item_tables():
    data = build_schema_data()
    catalog = next(domain for domain in data["domains"] if domain["id"] == "catalog")

    assert data["kinds"] == []
    assert catalog["tables"] == ["catalog_items", "catalog_item_identities"]
    assert {table["name"] for table in data["tables"]} == set(Base.metadata.tables) - HIDDEN_TABLE_NAMES
