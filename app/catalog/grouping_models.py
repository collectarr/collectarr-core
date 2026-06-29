from enum import StrEnum

from app.models.base import ItemKind


class GroupingModel(StrEnum):
    legacy_series_volume = "legacy_series_volume"
    release_based = "release_based"
    series_episode = "series_episode"
    work_release = "work_release"


LEGACY_SERIES_VOLUME_KINDS: frozenset[ItemKind] = frozenset(
    {ItemKind.book, ItemKind.comic, ItemKind.manga}
)


def grouping_model_for_kind(kind: ItemKind) -> GroupingModel:
    if kind in LEGACY_SERIES_VOLUME_KINDS:
        return GroupingModel.legacy_series_volume
    if kind == ItemKind.anime or kind == ItemKind.tv:
        return GroupingModel.series_episode
    return GroupingModel.work_release


def uses_legacy_series_volume(kind: ItemKind) -> bool:
    return grouping_model_for_kind(kind) is GroupingModel.legacy_series_volume
