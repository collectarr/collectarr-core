from __future__ import annotations

from app.models.base import Base


def test_tv_schema_contract_tables_exist():
    required = {
        "tv_series",
        "tv_seasons",
        "tv_episodes",
        "tv_releases",
        "tv_release_media",
    }

    assert required <= set(Base.metadata.tables)
