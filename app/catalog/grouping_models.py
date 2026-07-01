from enum import StrEnum

from app.models.base import ItemKind


class GroupingModel(StrEnum):
    book_series = "book_series"
    comic_volume = "comic_volume"
    manga_series = "manga_series"
    release_based = "release_based"
    series_episode = "series_episode"
    work_release = "work_release"


PRINT_GROUPING_KINDS: frozenset[ItemKind] = frozenset(
    {ItemKind.book, ItemKind.comic, ItemKind.manga}
)


def grouping_model_for_kind(kind: ItemKind) -> GroupingModel:
    if kind == ItemKind.book:
        return GroupingModel.book_series
    if kind == ItemKind.comic:
        return GroupingModel.comic_volume
    if kind == ItemKind.manga:
        return GroupingModel.manga_series
    if kind == ItemKind.anime or kind == ItemKind.tv:
        return GroupingModel.series_episode
    return GroupingModel.work_release


def uses_print_grouping(kind: ItemKind) -> bool:
    return kind in PRINT_GROUPING_KINDS
