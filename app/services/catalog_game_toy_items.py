from app.models.base import ItemKind
from app.models.catalog_game_toy_item import GameToyItem
from app.schemas.catalog_game_toy_item import CatalogGameToyItemResponse
from app.services.flat_inventory_items import FlatInventoryItemService


class CatalogGameToyItemService(FlatInventoryItemService[CatalogGameToyItemResponse]):
    kind = ItemKind.game_toy
    model = GameToyItem
    response_model = CatalogGameToyItemResponse
