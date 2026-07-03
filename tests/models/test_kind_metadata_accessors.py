from __future__ import annotations

from uuid import UUID

from app.models.canonical_board_games import (
    BoardGameCategory,
    BoardGameContribution,
    BoardGameEdition,
    BoardGameExpansion,
    BoardGameFamily,
    BoardGameIdentifier,
    BoardGameMechanic,
    BoardGameRankingSnapshot,
    BoardGameWork,
)
from app.models.canonical_games import (
    GameAgeRating,
    GameCompanyRole,
    GameIdentifier,
    GamePlatform,
    GameRelease,
    GameSeriesMembership,
    GameWork,
)
from app.models.canonical_support import Person


def test_game_metadata_accessors_normalize_lists():
    work = GameWork(
        title="Game",
        platform_entries=[
            GamePlatform(platform_name="PC", normalized_name="pc"),
            GamePlatform(platform_name="pc", normalized_name="pc"),
            GamePlatform(platform_name="PlayStation 5", normalized_name="playstation 5"),
        ],
        identifier_entries=[
            GameIdentifier(identifier_type="igdb", value="IGDB:1", normalized_value="IGDB:1"),
            GameIdentifier(identifier_type="igdb", value=" IGDB:1 ", normalized_value="IGDB:1"),
        ],
        company_role_entries=[
            GameCompanyRole(role="developer"),
            GameCompanyRole(role="publisher"),
        ],
        age_rating_entries=[GameAgeRating(rating_system="esrb", rating="E10+")],
        series_memberships=[
            GameSeriesMembership(
                series_name="Halo",
                normalized_series_name="halo",
                display_number="1",
            )
        ],
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
        identifier_entries=[
            BoardGameIdentifier(identifier_type="bgg", value="BGG:13", normalized_value="BGG:13"),
            BoardGameIdentifier(identifier_type="bgg", value="BGG:13", normalized_value="BGG:13"),
        ],
        contribution_entries=[
            BoardGameContribution(
                role="designer",
                person_id=UUID("00000000-0000-0000-0000-000000000003"),
                person=Person(name="Klaus Teuber"),
            ),
            BoardGameContribution(
                role="designer",
                person_id=UUID("00000000-0000-0000-0000-000000000003"),
                person=Person(name="Klaus Teuber"),
            ),
        ],
        mechanic_entries=[
            BoardGameMechanic(value="dice rolling", normalized_value="dice rolling"),
            BoardGameMechanic(value="resource management", normalized_value="resource management"),
        ],
        category_entries=[BoardGameCategory(value="economic", normalized_value="economic")],
        family_entries=[BoardGameFamily(value="catan", normalized_value="catan")],
        expansion_entries=[BoardGameExpansion(value="Seafarers", normalized_value="seafarers")],
        ranking_snapshots=[
            BoardGameRankingSnapshot(ranking_name="BGG Rank #1", rank_position=1),
        ],
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
