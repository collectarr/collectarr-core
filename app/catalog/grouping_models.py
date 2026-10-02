from enum import StrEnum

from app.models.base import ItemKind


class GroupingModel(StrEnum):
    book_series = "book_series"
    catalog_item = "catalog_item"
    series_episode = "series_episode"


PRINT_GROUPING_KINDS: frozenset[ItemKind] = frozenset(
    {ItemKind.book, ItemKind.comic, ItemKind.manga}
)


def grouping_model_for_kind(kind: ItemKind) -> GroupingModel:
    if kind in {
        ItemKind.anime,
        ItemKind.boardgame,
        ItemKind.game,
        ItemKind.manga,
        ItemKind.movie,
        ItemKind.music,
        ItemKind.tv,
    }:
        return GroupingModel.catalog_item
    if kind == ItemKind.book:
        return GroupingModel.book_series
    if kind == ItemKind.comic:
        return GroupingModel.catalog_item
    return GroupingModel.catalog_item


def uses_print_grouping(kind: ItemKind) -> bool:
    return kind in PRINT_GROUPING_KINDS
