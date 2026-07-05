from collections import deque
from datetime import UTC, date, datetime, timedelta
from enum import Enum as PythonEnum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminAuditLog,
    AnimeSeries,
    BoardGameWork,
    BookWork,
    ComicWork,
    ExternalProviderId,
    GameWork,
    MangaWork,
    MovieWork,
    ProviderIngestJob,
    TVRelease,
    TVSeries,
)
from app.schemas import ExternalProviderIdResponse
from app.schemas.admin import ProviderIngestHistoryEntry
from app.search.client import SearchClient
from app.search.documents import catalog_search_document
from app.services.metadata import MetadataService

_INGEST_HISTORY: deque[ProviderIngestHistoryEntry] = deque(maxlen=50)
_INGEST_HISTORY_SEQUENCE = 0


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

    async def provider_links_for_entities(
        self,
        entity_type: str,
        entity_ids: list[UUID],
    ) -> dict[UUID, list[ExternalProviderIdResponse]]:
        if not entity_ids:
            return {}
        result = await self.db.execute(
            select(ExternalProviderId)
            .where(
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.entity_id.in_(entity_ids),
            )
            .order_by(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
        )
        links_by_entity: dict[UUID, list[ExternalProviderIdResponse]] = {}
        for row in result.scalars():
            links_by_entity.setdefault(row.entity_id, []).append(
                ExternalProviderIdResponse(
                    provider=row.provider,
                    entity_type=row.entity_type,
                    provider_item_id=row.provider_item_id,
                    site_url=row.site_url,
                    api_url=row.api_url,
                )
            )
        return links_by_entity

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

    def ingest_history(self) -> list[ProviderIngestHistoryEntry]:
        return list(_INGEST_HISTORY)

    def record_ingest_history(
        self,
        *,
        payload: Any,
        status: str,
        attempts: int,
        resolved_entity_type: str | None = None,
        resolved_entity_id: UUID | None = None,
        error: str | None = None,
    ) -> None:
        global _INGEST_HISTORY_SEQUENCE
        _INGEST_HISTORY_SEQUENCE += 1
        _INGEST_HISTORY.appendleft(
            ProviderIngestHistoryEntry(
                id=_INGEST_HISTORY_SEQUENCE,
                timestamp=datetime.now(UTC),
                provider=payload.provider,
                provider_item_id=payload.provider_item_id,
                status=status,
                attempts=attempts,
                resolved_entity_type=resolved_entity_type,
                resolved_entity_id=resolved_entity_id,
                error=error,
            )
        )

    def record_admin_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            AdminAuditLog(
                action=action,
                actor_user_id=self.actor_user_id,
                actor_email=self.actor_email,
                entity_type=entity_type,
                entity_id=entity_id,
                details_json=self._audit_json_safe(details or {}),
            )
        )

    def ingest_job_audit_details(self, job: ProviderIngestJob) -> dict[str, Any]:
        return {
            "provider": job.provider,
            "provider_item_id": job.provider_item_id,
            "status": job.status,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "resolved_entity_type": job.resolved_entity_type,
            "resolved_entity_id": job.resolved_entity_id,
            "last_error": job.last_error,
        }

    async def reindex_items(self, item_ids: set[UUID]) -> None:
        documents: list[dict[str, Any]] = []
        if not item_ids:
            return
        for model in (BookWork, ComicWork, MangaWork, AnimeSeries, MovieWork, TVRelease, GameWork, BoardGameWork):
            model_result = await self.db.execute(select(model).where(model.id.in_(item_ids)))
            documents.extend(
                catalog_search_document(entity)
                for entity in model_result.scalars().unique()
            )
        if documents:
            await SearchClient().index_documents_best_effort(documents)

    def backoff_delay(self, attempts: int) -> timedelta:
        return timedelta(seconds=min(300, 5 * (2 ** max(0, attempts - 1))))

    def is_retryable_ingest_error(self, error: Exception) -> bool:
        if isinstance(error, HTTPException):
            return error.status_code in {
                status.HTTP_429_TOO_MANY_REQUESTS,
                status.HTTP_502_BAD_GATEWAY,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_504_GATEWAY_TIMEOUT,
            }
        return False

    def error_message(self, error: Exception) -> str:
        if isinstance(error, HTTPException):
            return str(error.detail)
        return str(error)

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