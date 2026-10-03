"""Composition point for kind-owned Catalog Item document schemas."""

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
from app.models.base import ItemKind

DOCUMENTS: dict[ItemKind, KindDocumentShape] = {
    ItemKind.anime: anime.DOCUMENT,
    ItemKind.boardgame: boardgame.DOCUMENT,
    ItemKind.book: book.DOCUMENT,
    ItemKind.comic: comic.DOCUMENT,
    ItemKind.game: game.DOCUMENT,
    ItemKind.manga: manga.DOCUMENT,
    ItemKind.movie: movie.DOCUMENT,
    ItemKind.music: music.DOCUMENT,
    ItemKind.tv: tv.DOCUMENT,
}


def document_for(kind: ItemKind) -> KindDocumentShape:
    try:
        return DOCUMENTS[kind]
    except KeyError as error:
        raise ValueError(f"No Catalog Item document schema for kind: {kind}") from error
