from __future__ import annotations

from app.services.anime_service import AnimeService
from app.services.boardgames_service import BoardGamesService
from app.services.books_service import BooksService
from app.services.comics_service import ComicsService
from app.services.games_service import GamesService
from app.services.manga_service import MangaService
from app.services.metadata.field_schema_service import FieldSchemaService
from app.services.metadata.metadata_common_support import MetadataCommonSupport
from app.services.metadata.metadata_response_builders import MetadataResponseBuilders
from app.services.metadata.metadata_typed_reads import MetadataTypedReadService
from app.services.movies_service import MoviesService
from app.services.music_service import MusicService
from app.services.tv_service import TVService


class MetadataReadService(
    MetadataCommonSupport,
    MetadataTypedReadService,
    MetadataResponseBuilders,
    BooksService,
    MoviesService,
    TVService,
    AnimeService,
    MusicService,
    BoardGamesService,
    GamesService,
    MangaService,
    ComicsService,
    FieldSchemaService,
):
    """Composed typed read surface mixed directly into MetadataFacade."""
