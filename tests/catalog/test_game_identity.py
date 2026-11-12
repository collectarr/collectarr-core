from uuid import uuid4

import pytest

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.catalog.kind_documents.game_identity import game_level_document, is_game_edition
from app.models.base import ItemKind
from app.models.catalog_game_item import GameItem
from app.services.catalog_game_items import _response


def test_game_and_media_ids_have_distinct_meanings():
    game = GameItem(id=uuid4(), title="Game", details={}, revision=1)
    edition = GameItem(id=uuid4(), parent_game_id=game.id, title="Edition", details={}, revision=1)
    assert _response(game).game_id == game.id
    assert _response(game).media_id is None
    assert _response(edition).game_id == game.id
    assert _response(edition).media_id == edition.id


def test_game_level_copy_does_not_keep_edition_specific_data():
    edition = {"title": "Game", "platforms": ["PS5"], "barcode": "123",
               "release_region": "EU", "cover_image_url": "edition.webp"}
    assert is_game_edition(edition)
    game = game_level_document(edition)
    assert game == {"title": "Game", "platforms": ["PS5"]}
    assert not is_game_edition(game)
    assert edition["barcode"] == "123"


def test_creation_accepts_a_game_link_but_never_a_client_assigned_media_id():
    link = str(uuid4())
    assert validate_catalog_item_payload(ItemKind.game, {"title": "Edition", "game_id": link})["game_id"] == link
    with pytest.raises(ValueError, match="UUID"):
        validate_catalog_item_payload(ItemKind.game, {"title": "Edition", "game_id": "invalid"})
    with pytest.raises(ValueError):
        validate_catalog_item_payload(ItemKind.game, {"title": "Edition", "media_id": link})
