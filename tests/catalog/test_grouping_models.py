from app.catalog.grouping_models import (
    GroupingModel,
    grouping_model_for_kind,
    uses_print_grouping,
)
from app.models.base import ItemKind


def test_grouping_model_classification_matches_current_kind_split():
    assert grouping_model_for_kind(ItemKind.book) is GroupingModel.book_series
    assert grouping_model_for_kind(ItemKind.comic) is GroupingModel.catalog_item
    assert grouping_model_for_kind(ItemKind.manga) is GroupingModel.catalog_item
    assert grouping_model_for_kind(ItemKind.anime) is GroupingModel.catalog_item
    assert grouping_model_for_kind(ItemKind.movie) is GroupingModel.catalog_item
    assert grouping_model_for_kind(ItemKind.music) is GroupingModel.catalog_item


def test_print_grouping_gate_is_explicit():
    assert uses_print_grouping(ItemKind.book) is True
    assert uses_print_grouping(ItemKind.music) is False
