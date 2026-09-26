from datetime import date, datetime
from enum import Enum as PythonEnum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminAuditLog,
    AdminAuditLogDetail,
    AnimeSeries,
    BoardGameWork,
    BookWork,
    ComicWork,
    GameWork,
    MangaWork,
    MovieWork,
    MusicAlbum,
    Tag,
    TVRelease,
    TVSeries,
)
from app.search.client import SearchClient
from app.search.documents import catalog_search_document
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
        for model in (BookWork, ComicWork, MangaWork, AnimeSeries, MovieWork, TVRelease, GameWork, BoardGameWork, MusicAlbum):
            model_result = await self.db.execute(select(model).where(model.id.in_(item_ids)))
            documents.extend(
                catalog_search_document(entity)
                for entity in model_result.scalars().unique()
            )
        if documents:
            await SearchClient().index_documents_best_effort(documents)

    def _audit_json_safe(self, value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime | date):
            return value.isoformat()
        if isinstance(value, PythonEnum):
            return value.value
        if isinstance(value, dict):
            return {str(key): self._audit_json_safe(item) for key, item in value.items()}
        if isinstance(value, list | tuple | set):
            return [self._audit_json_safe(item) for item in value]
        return value

    async def _native_item_response(self, item: Any) -> Any | None:
        metadata = MetadataService(self.db)
        if isinstance(item, BookWork):
            return await metadata.get_book_work(item.id)
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
