from app.models.base import ItemKind
from app.models.catalog_game_hardware_item import GameHardwareItem
from app.schemas.catalog_game_hardware_item import CatalogGameHardwareItemResponse
from app.services.flat_inventory_items import FlatInventoryItemService


class CatalogGameHardwareItemService(FlatInventoryItemService[CatalogGameHardwareItemResponse]):
    kind = ItemKind.game_hardware
    model = GameHardwareItem
    response_model = CatalogGameHardwareItemResponse
