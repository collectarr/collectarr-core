from app.catalog.media_types import top_level_media_types
from app.models.base import ItemKind
from app.providers.registry import ProviderRegistry

ACTIVE_PARITY_KINDS = {
    ItemKind.comic,
    ItemKind.manga,
    ItemKind.anime,
    ItemKind.book,
    ItemKind.game,
    ItemKind.boardgame,
    ItemKind.movie,
    ItemKind.tv,
    ItemKind.music,
}


def test_active_top_level_kinds_match_parity_contract():
    top_level_kinds = {media_type.kind for media_type in top_level_media_types}

    assert top_level_kinds == ACTIVE_PARITY_KINDS
    # Internal kinds must not become active top-level routes.
    assert ItemKind.collection not in top_level_kinds


def test_every_active_kind_has_default_provider_in_its_provider_list():
    for media_type in top_level_media_types:
        assert media_type.default_provider is not None
        assert media_type.default_provider in media_type.providers


def test_provider_registry_exposes_provider_coverage_for_every_active_kind():
    registry = ProviderRegistry()

    for kind in ACTIVE_PARITY_KINDS:
        providers = registry.for_kind(kind)
        assert providers

        default_provider = registry.default_for_kind(kind)
        assert default_provider is not None
        assert default_provider in providers
