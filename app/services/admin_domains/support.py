from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AnimeItem,
    AdminAuditLog,
    AdminAuditLogDetail,
    AnimeSeries,
    BoardGameItem,
    BoardGameWork,
    BookItem,
    ComicItem,
    ComicWork,
    GameItem,
    GameWork,
    MangaItem,
    MangaWork,
    MovieItem,
    MovieWork,
    MusicItem,
    Tag,
    TVRelease,
    TVSeries,
    TvItem,
)
from app.search.client import SearchClient
from app.search.documents import catalog_search_document
from app.services.catalog_boardgame_items import CatalogBoardGameItemService
from app.services.catalog_book_items import CatalogBookItemService
from app.services.catalog_comic_items import CatalogComicItemService
from app.services.catalog_game_items import CatalogGameItemService
from app.services.catalog_manga_items import CatalogMangaItemService
from app.services.catalog_music_items import CatalogMusicItemService
from app.services.catalog_movie_items import CatalogMovieItemService
from app.services.catalog_series_items import (
    CatalogAnimeItemService,
    CatalogTvItemService,
)
from app.services.facade import MetadataFacade as MetadataService
from app.services.typed_values import flatten_typed_values


class AdminSupportService:
    def __init__(
        self,
        *,
        db: AsyncSession,
        actor_user_id: UUID | None,
        actor_email: str | None,
    ) -> None:
        self.db = db
        self.actor_user_id = actor_user_id
        self.actor_email = actor_email

    async def get_or_create_tag(self, kind: str, name: str) -> Tag:
        result = await self.db.execute(select(Tag).where(Tag.kind == kind, Tag.name == name))
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(kind=kind, name=name)
            self.db.add(tag)
            await self.db.flush()
        return tag

    async def item_response(self, item: Any) -> Any:
        native_response = await self._native_item_response(item)
        if native_response is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Native catalog entity response unavailable",
            )
        return native_response

    async def item_responses(self, items: list[Any]) -> list[Any]:
        responses: list[Any] = []
        for item in items:
            native_response = await self._native_item_response(item)
            if native_response is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Native catalog entity response unavailable",
                )
            responses.append(native_response)
        return responses

    def record_admin_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        audit_log = AdminAuditLog(
            action=action,
            actor_user_id=self.actor_user_id,
            actor_email=self.actor_email,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        audit_log.details = [
            AdminAuditLogDetail(**row) for row in flatten_typed_values(details or {})
        ]
        self.db.add(audit_log)

    async def reindex_items(self, item_ids: set[UUID]) -> None:
        documents: list[dict[str, Any]] = []
        if not item_ids:
            return
        flat_root_options = {
            BookItem: [
                selectinload(BookItem.identifiers),
                selectinload(BookItem.credits),
            ],
            ComicItem: [selectinload(ComicItem.identifiers)],
            MangaItem: [selectinload(MangaItem.identifiers)],
            AnimeItem: [selectinload(AnimeItem.identifiers)],
            GameItem: [selectinload(GameItem.identifiers)],
            BoardGameItem: [selectinload(BoardGameItem.identifiers)],
            TvItem: [selectinload(TvItem.identifiers)],
        }
        for model in (
            ComicWork, MangaWork, AnimeSeries, MovieWork, TVRelease,
            GameWork, BoardGameWork, MusicItem, MovieItem,
            BookItem, ComicItem, MangaItem, AnimeItem, GameItem, BoardGameItem, TvItem,
        ):
            statement = select(model).where(model.id.in_(item_ids))
            statement = statement.options(*flat_root_options.get(model, []))
            model_result = await self.db.execute(statement)
            documents.extend(
                catalog_search_document(entity)
                for entity in model_result.scalars().unique()
            )
        if documents:
            await SearchClient().index_documents_best_effort(documents)

    async def _native_item_response(self, item: Any) -> Any | None:
        if isinstance(item, MusicItem):
            response = await CatalogMusicItemService(self.db).get(item.id)
            return response.model_dump(mode="json")
        if isinstance(item, MovieItem):
            response = await CatalogMovieItemService(self.db).get(item.id)
            return response.model_dump(mode="json")
        if isinstance(item, BookItem):
            response = await CatalogBookItemService(self.db).get(item.id)
            return response.model_dump(mode="json")
        if isinstance(item, ComicItem):
            response = await CatalogComicItemService(self.db).get(item.id)
            return response.model_dump(mode="json")
        if isinstance(item, MangaItem):
            response = await CatalogMangaItemService(self.db).get(item.id)
            return response.model_dump(mode="json")
        if isinstance(item, AnimeItem):
            response = await CatalogAnimeItemService(self.db).get(item.id)
            return response.model_dump(mode="json")
        if isinstance(item, GameItem):
            response = await CatalogGameItemService(self.db).get(item.id)
            return response.model_dump(mode="json")
        if isinstance(item, BoardGameItem):
            response = await CatalogBoardGameItemService(self.db).get(item.id)
            return response.model_dump(mode="json")
        if isinstance(item, TvItem):
            response = await CatalogTvItemService(self.db).get(item.id)
            return response.model_dump(mode="json")
        metadata = MetadataService(self.db)
        if isinstance(item, ComicWork):
            return await metadata.get_comic_work(item.id)
        if isinstance(item, MangaWork):
            return await metadata.get_manga_work(item.id)
        if isinstance(item, AnimeSeries):
            return await metadata.get_anime_series(item.id)
        if isinstance(item, MovieWork):
            return await metadata.get_movie_work(item.id)
        if isinstance(item, TVSeries):
            return await metadata.get_tv_series(item.id)
        if isinstance(item, TVRelease):
            return await metadata.get_tv_series(item.series_id)
        if isinstance(item, GameWork):
            return await metadata.get_game_work(item.id)
        if isinstance(item, BoardGameWork):
            return await metadata.get_boardgame_work(item.id)
        return None
