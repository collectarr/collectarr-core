from app.catalog.grouping_models import (
    GroupingModel,
    grouping_model_for_kind,
    uses_legacy_series_volume,
)
from app.models.base import ItemKind


def test_grouping_model_classification_matches_current_kind_split():
    assert grouping_model_for_kind(ItemKind.book) is GroupingModel.legacy_series_volume
    assert grouping_model_for_kind(ItemKind.comic) is GroupingModel.legacy_series_volume
    assert grouping_model_for_kind(ItemKind.manga) is GroupingModel.legacy_series_volume
    assert grouping_model_for_kind(ItemKind.anime) is GroupingModel.series_episode
    assert grouping_model_for_kind(ItemKind.movie) is GroupingModel.work_release
    assert grouping_model_for_kind(ItemKind.music) is GroupingModel.work_release


def test_legacy_series_volume_gate_is_explicit():
    assert uses_legacy_series_volume(ItemKind.book) is True
    assert uses_legacy_series_volume(ItemKind.music) is False
