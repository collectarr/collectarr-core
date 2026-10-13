from __future__ import annotations

from uuid import UUID

from app.models.catalog_boardgame_item import BoardGameItem
from app.models.catalog_game_item import GameItem
from app.services.catalog_boardgame_items import _response as boardgame_response
from app.services.catalog_game_items import _response as game_response


def test_game_catalog_item_response_projects_flat_edition_details():
    item = GameItem(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        title="Game",
        revision=1,
        details={
            "platforms": ["PC", "PlayStation 5"],
            "company_roles": ["developer", "publisher"],
            "release_region": "US",
            "physical_format": "disc",
            "identifiers": [
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "identifier_type": "sku",
                    "value": "SKU-1",
                    "normalized_value": "sku1",
                    "is_primary": True,
                }
            ],
        },
    )

    response = game_response(item)

    assert response.kind == "game"
    assert response.platforms == ["PC", "PlayStation 5"]
    assert response.company_roles == ["developer", "publisher"]
    assert response.release_region == "US"
    assert response.physical_format == "disc"
    assert response.identifiers[0].value == "SKU-1"


def test_board_game_catalog_item_response_projects_flat_edition_details():
    item = BoardGameItem(
        id=UUID("00000000-0000-0000-0000-000000000003"),
        title="Board Game",
        revision=1,
        details={
            "year_published": 1995,
            "min_players": 2,
            "max_players": 4,
            "playing_time_minutes": 60,
            "contributors": [{"name": "Klaus Teuber", "role": "designer"}],
            "mechanics": ["trading", "building"],
            "categories": ["economic"],
            "identifiers": [
                {
                    "id": "00000000-0000-0000-0000-000000000004",
                    "identifier_type": "catalog_number",
                    "value": "BG-1",
                    "normalized_value": "bg1",
                    "is_primary": True,
                }
            ],
        },
    )

    response = boardgame_response(item)

    assert response.kind == "boardgame"
    assert response.year_published == 1995
    assert response.min_players == 2
    assert response.max_players == 4
    assert response.playing_time_minutes == 60
    assert response.contributors == [{"name": "Klaus Teuber", "role": "designer"}]
    assert response.mechanics == ["trading", "building"]
    assert response.categories == ["economic"]
    assert response.identifiers[0].value == "BG-1"
