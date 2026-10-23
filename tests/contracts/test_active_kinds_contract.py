from app.catalog.media_types import top_level_media_types
from app.models.base import ItemKind

ACTIVE_PARITY_KINDS = {ItemKind.music, ItemKind.game}


def test_active_top_level_kinds_match_parity_contract():
    top_level_kinds = {media_type.kind for media_type in top_level_media_types}

    assert top_level_kinds == ACTIVE_PARITY_KINDS
    # Internal kinds must not become active top-level routes.
    assert ItemKind.collection not in top_level_kinds
    assert not {ItemKind.game_hardware, ItemKind.game_toy} & top_level_kinds
