from __future__ import annotations

from uuid import UUID

from app.models.canonical_board_games import BoardGameEdition, BoardGameWork
from app.models.canonical_games import GameRelease, GameWork


def test_game_metadata_accessors_normalize_lists():
    work = GameWork(
        title="Game",
        metadata_json={
            "platforms": ["PC", "pc", "PlayStation 5", " "],
            "identifiers": ["IGDB:1", " IGDB:1 ", None],
            "company_roles": ["developer", "publisher"],
            "age_ratings": ["E10+"],
        },
    )
    release = GameRelease(
        work_id=UUID("00000000-0000-0000-0000-000000000001"),
        metadata_json={"identifiers": ["Release:1", "release:1", "SKU-1"]},
    )

    assert work.platforms == ["PC", "PlayStation 5"]
    assert work.identifiers == ["IGDB:1"]
    assert work.company_roles == ["developer", "publisher"]
    assert work.age_ratings == ["E10+"]
    assert release.identifiers == ["Release:1", "SKU-1"]


def test_boardgame_metadata_accessors_normalize_lists():
    work = BoardGameWork(
        title="Board Game",
        metadata_json={
            "identifiers": ["BGG:13", "BGG:13"],
            "contributors": ["Klaus Teuber", "klaus teuber"],
            "mechanics": ["dice rolling", "resource management"],
            "categories": ["economic"],
            "families": ["catan"],
            "expansions": ["Seafarers"],
            "rankings": ["BGG Rank #1"],
        },
    )
    edition = BoardGameEdition(
        work_id=UUID("00000000-0000-0000-0000-000000000002"),
        metadata_json={"identifiers": ["ED:1", "ed:1", "ED:2"]},
    )

    assert work.identifiers == ["BGG:13"]
    assert work.contributors == ["Klaus Teuber"]
    assert work.mechanics == ["dice rolling", "resource management"]
    assert work.categories == ["economic"]
    assert work.families == ["catan"]
    assert work.expansions == ["Seafarers"]
    assert work.rankings == ["BGG Rank #1"]
    assert edition.identifiers == ["ED:1", "ED:2"]
