from __future__ import annotations

from app.models.base import Base


def test_flat_tv_catalog_schema_contract_tables_exist():
    required = {
        "tv_items",
        "tv_item_seasons",
        "tv_item_episodes",
        "tv_item_media",
        "tv_item_identifiers",
    }

    assert required <= set(Base.metadata.tables)
    assert not {
        "tv_series",
        "tv_seasons",
        "tv_episodes",
        "tv_releases",
        "tv_release_media",
    } & set(Base.metadata.tables)
