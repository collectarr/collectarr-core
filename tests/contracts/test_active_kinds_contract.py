from app.models.base import ItemKind
from app.schemas.catalog_item_v1 import CATALOG_ITEM_DETAILS_BY_KIND


def test_active_catalog_kinds_match_typed_item_schemas():
    active_kinds = {kind.value for kind in ItemKind}

    assert active_kinds == set(CATALOG_ITEM_DETAILS_BY_KIND)
    assert len(active_kinds) == 9
