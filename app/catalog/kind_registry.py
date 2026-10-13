"""Composition point for the nine canonical Catalog Item kinds."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from app.catalog.document_shape import KindDocumentShape
from app.catalog.kind_documents import (
    anime,
    boardgame,
    book,
    comic,
    game,
    manga,
    movie,
    music,
    tv,
)
from app.catalog.metadata_field_spec import MetadataFieldSpec
from app.catalog.physical_formats import PhysicalFormatConfig, video_physical_formats
from app.models.base import ItemKind
from app.models.catalog_anime_item import AnimeItem
from app.models.catalog_boardgame_item import BoardGameItem
from app.models.catalog_book_item import BookItem
from app.models.catalog_comic_item import ComicItem
from app.models.catalog_game_item import GameItem
from app.models.catalog_manga_item import MangaItem
from app.models.catalog_movie_item import MovieItem
from app.models.catalog_music_item import MusicItem
from app.models.catalog_tv_item import TvItem


@dataclass(frozen=True)
class CatalogKindDefinition:
    """Static registration metadata for one source-neutral catalog kind."""

    kind: ItemKind
    document: KindDocumentShape
    model: type
    response_model_module: str
    response_model_name: str
    proposal_writer_module: str
    proposal_writer_name: str
    route_module: str
    entity_type: str
    singular_label: str
    plural_label: str
    route_segments: tuple[str, ...]
    field_specs: tuple[MetadataFieldSpec, ...]
    item_number_sort_padding: int | None = None
    physical_formats: tuple[PhysicalFormatConfig, ...] = ()
    search_sort_column: object | None = None
    search_document_function: str = "flat_catalog_item_search_document"
    search_document_uses_kind: bool = True
    contained_count_fields: tuple[str, ...] = ()

    @property
    def table_name(self) -> str:
        return self.model.__tablename__

    @property
    def response_model(self) -> Any:
        """Load the Pydantic response lazily to avoid schema registry cycles."""
        module = import_module(self.response_model_module)
        return getattr(module, self.response_model_name)

    @property
    def proposal_writer(self) -> type[Any]:
        module = import_module(self.proposal_writer_module)
        return getattr(module, self.proposal_writer_name)

    @property
    def router(self) -> Any:
        module = import_module(self.route_module)
        return module.router

    def search_document(self, item: Any) -> dict[str, Any]:
        module = import_module("app.search.documents")
        builder = getattr(module, self.search_document_function)
        if self.search_document_uses_kind:
            return builder(item, self.kind)
        return builder(item)


CATALOG_KIND_DEFINITIONS: tuple[CatalogKindDefinition, ...] = tuple(
    sorted(
        (
            CatalogKindDefinition(
                kind=ItemKind.comic,
                document=comic.DOCUMENT,
                model=ComicItem,
                response_model_module="app.schemas.catalog_comic_item",
                response_model_name="CatalogComicItemResponse",
                proposal_writer_module="app.services.catalog_comic_items",
                proposal_writer_name="CatalogComicItemService",
                route_module="app.api.routes.metadata.catalog_comic_items",
                entity_type="catalog_comic_item",
                singular_label="Comic",
                plural_label="Comics",
                route_segments=("comics", "comic"),
                field_specs=comic.FIELD_SPECS,
                item_number_sort_padding=6,
                contained_count_fields=("identifiers",),
            ),
            CatalogKindDefinition(
                kind=ItemKind.manga,
                document=manga.DOCUMENT,
                model=MangaItem,
                response_model_module="app.schemas.catalog_manga_item",
                response_model_name="CatalogMangaItemResponse",
                proposal_writer_module="app.services.catalog_manga_items",
                proposal_writer_name="CatalogMangaItemService",
                route_module="app.api.routes.metadata.catalog_manga_items",
                entity_type="catalog_manga_item",
                singular_label="Manga",
                plural_label="Manga",
                route_segments=("manga",),
                field_specs=manga.FIELD_SPECS,
                contained_count_fields=("identifiers",),
            ),
            CatalogKindDefinition(
                kind=ItemKind.anime,
                document=anime.DOCUMENT,
                model=AnimeItem,
                response_model_module="app.schemas.catalog_anime_item",
                response_model_name="CatalogAnimeItemResponse",
                proposal_writer_module="app.services.catalog_series_items",
                proposal_writer_name="CatalogAnimeItemService",
                route_module="app.api.routes.metadata.catalog_anime_items",
                entity_type="catalog_anime_item",
                singular_label="Anime",
                plural_label="Anime",
                route_segments=("anime",),
                field_specs=anime.FIELD_SPECS,
                physical_formats=video_physical_formats,
                contained_count_fields=("media", "episodes", "identifiers"),
            ),
            CatalogKindDefinition(
                kind=ItemKind.movie,
                document=movie.DOCUMENT,
                model=MovieItem,
                response_model_module="app.schemas.catalog_movie_item",
                response_model_name="CatalogMovieItemResponse",
                proposal_writer_module="app.services.catalog_movie_items",
                proposal_writer_name="CatalogMovieItemService",
                route_module="app.api.routes.metadata.catalog_movie_items",
                entity_type="catalog_movie_item",
                singular_label="Movie",
                plural_label="Movies",
                route_segments=("movies", "movie"),
                field_specs=movie.FIELD_SPECS,
                physical_formats=video_physical_formats,
                search_document_function="movie_item_search_document",
                search_document_uses_kind=False,
                contained_count_fields=("media",),
            ),
            CatalogKindDefinition(
                kind=ItemKind.tv,
                document=tv.DOCUMENT,
                model=TvItem,
                response_model_module="app.schemas.catalog_tv_item",
                response_model_name="CatalogTvItemResponse",
                proposal_writer_module="app.services.catalog_series_items",
                proposal_writer_name="CatalogTvItemService",
                route_module="app.api.routes.metadata.catalog_tv_items",
                entity_type="catalog_tv_item",
                singular_label="TV Show",
                plural_label="TV Shows",
                route_segments=("tv", "shows", "series"),
                field_specs=tv.FIELD_SPECS,
                physical_formats=video_physical_formats,
                contained_count_fields=("seasons", "media", "episodes", "identifiers"),
            ),
            CatalogKindDefinition(
                kind=ItemKind.game,
                document=game.DOCUMENT,
                model=GameItem,
                response_model_module="app.schemas.catalog_game_item",
                response_model_name="CatalogGameItemResponse",
                proposal_writer_module="app.services.catalog_game_items",
                proposal_writer_name="CatalogGameItemService",
                route_module="app.api.routes.metadata.catalog_game_items",
                entity_type="catalog_game_item",
                singular_label="Game",
                plural_label="Games",
                route_segments=("games", "game"),
                field_specs=game.FIELD_SPECS,
                contained_count_fields=("identifiers",),
            ),
            CatalogKindDefinition(
                kind=ItemKind.boardgame,
                document=boardgame.DOCUMENT,
                model=BoardGameItem,
                response_model_module="app.schemas.catalog_boardgame_item",
                response_model_name="CatalogBoardGameItemResponse",
                proposal_writer_module="app.services.catalog_boardgame_items",
                proposal_writer_name="CatalogBoardGameItemService",
                route_module="app.api.routes.metadata.catalog_boardgame_items",
                entity_type="catalog_boardgame_item",
                singular_label="Board Game",
                plural_label="Board Games",
                route_segments=("board-games", "boardgames", "boardgame"),
                field_specs=boardgame.FIELD_SPECS,
                contained_count_fields=("identifiers",),
            ),
            CatalogKindDefinition(
                kind=ItemKind.book,
                document=book.DOCUMENT,
                model=BookItem,
                response_model_module="app.schemas.catalog_book_item",
                response_model_name="CatalogBookItemResponse",
                proposal_writer_module="app.services.catalog_book_items",
                proposal_writer_name="CatalogBookItemService",
                route_module="app.api.routes.metadata.catalog_book_items",
                entity_type="catalog_book_item",
                singular_label="Book",
                plural_label="Books",
                route_segments=("books", "book"),
                field_specs=book.FIELD_SPECS,
                contained_count_fields=(
                    "printings",
                    "credits",
                    "identifiers",
                    "series_memberships",
                ),
            ),
            CatalogKindDefinition(
                kind=ItemKind.music,
                document=music.DOCUMENT,
                model=MusicItem,
                response_model_module="app.schemas.catalog_music_item",
                response_model_name="CatalogMusicItemResponse",
                proposal_writer_module="app.services.catalog_music_items",
                proposal_writer_name="CatalogMusicItemService",
                route_module="app.api.routes.metadata.catalog_music_items",
                entity_type="catalog_music_item",
                singular_label="Music Release",
                plural_label="Music Releases",
                route_segments=("music",),
                field_specs=music.FIELD_SPECS,
                search_sort_column=MusicItem.sort_title,
                search_document_function="music_item_search_document",
                search_document_uses_kind=False,
                contained_count_fields=("discs",),
            ),
        ),
        key=lambda definition: definition.kind.value,
    )
)

CATALOG_KINDS_BY_ID = {definition.kind: definition for definition in CATALOG_KIND_DEFINITIONS}
CATALOG_KINDS_BY_MODEL = {definition.model: definition for definition in CATALOG_KIND_DEFINITIONS}
CATALOG_KINDS_BY_ROUTE = {
    segment: definition
    for definition in CATALOG_KIND_DEFINITIONS
    for segment in definition.route_segments
}


def catalog_kind_for(kind: ItemKind) -> CatalogKindDefinition:
    try:
        return CATALOG_KINDS_BY_ID[kind]
    except KeyError as error:
        raise ValueError(f"No Catalog Item kind definition for {kind}") from error
