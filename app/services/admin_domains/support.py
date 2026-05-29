from collections import deque
from datetime import UTC, date, datetime, timedelta
from enum import Enum as PythonEnum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canonical import AdminAuditLog, Item, ItemProviderLink, ProviderIngestJob
from app.schemas.admin import ProviderIngestHistoryEntry
from app.schemas.metadata import ProviderLink, item_response_from_model
from app.search.client import SearchClient
from app.search.documents import item_search_document
from app.repositories.metadata import MetadataRepository


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

    async def provider_links_for_items(self, item_ids: list[UUID]) -> dict[UUID, list[ProviderLink]]:
        if not item_ids:
            return {}
        result = await self.db.execute(
            select(ItemProviderLink)
            .where(
                ItemProviderLink.item_id.in_(item_ids),
            )
            .order_by(ItemProviderLink.provider, ItemProviderLink.provider_item_id)
        )
        links_by_item: dict[UUID, list[ProviderLink]] = {}
        for row in result.scalars():
            links_by_item.setdefault(row.item_id, []).append(
                ProviderLink(
                    provider=row.provider,
                    entity_type="item",
                    provider_item_id=row.provider_item_id,
                    site_url=row.site_url,
                    api_url=row.api_url,
                )
            )
        return links_by_item

    async def item_response(self, item: Item) -> Any:
        links_by_item = await self.provider_links_for_items([item.id])
        return item_response_from_model(item, extra_provider_links=links_by_item.get(item.id))

    async def item_responses(self, items: list[Item]) -> list[Any]:
        links_by_item = await self.provider_links_for_items([item.id for item in items])
        return [
            item_response_from_model(item, extra_provider_links=links_by_item.get(item.id))
            for item in items
        ]

    def ingest_history(self) -> list[ProviderIngestHistoryEntry]:
        return list(_INGEST_HISTORY)

    def record_ingest_history(
        self,
        *,
        payload: Any,
        status: str,
        attempts: int,
        item_id: UUID | None = None,
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
                item_id=item_id,
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
            "item_id": job.item_id,
            "last_error": job.last_error,
        }

    async def reindex_items(self, item_ids: set[UUID]) -> None:
        documents: list[dict[str, Any]] = []
        repository = MetadataRepository(self.db)
        for item_id in item_ids:
            loaded_item = await repository.get_item(item_id)
            if loaded_item is not None:
                documents.append(item_search_document(loaded_item))
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