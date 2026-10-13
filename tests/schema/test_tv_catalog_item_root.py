from app.models.base import ItemKind
from app.models.catalog_tv_item import TvItem
from app.models.entity_refs import DEFAULT_ENTITY_REF_REGISTRY
from app.services.catalog_series_items import CatalogTvItemService


def test_unreleased_tv_root_is_not_registered():
    assert DEFAULT_ENTITY_REF_REGISTRY.table_name("catalog_tv_item") is None
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("tv_series")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("tv_release")
    assert not DEFAULT_ENTITY_REF_REGISTRY.is_known("tv_episode")


def test_tv_catalog_service_reads_flat_catalog_items():
    assert CatalogTvItemService.kind is ItemKind.tv
    assert CatalogTvItemService.item_model is TvItem
