from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ApiHTTPException
from app.models import (
    AdminAuditLog,
    AdminAuditLogDetail,
    DuplicateReview,
    DuplicateReviewDetail,
    DuplicateReviewEntity,
)
from app.models.canonical_catalog_items import CanonicalCatalogItem
from app.schemas.admin import (
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateQueueSummaryResponse,
    AdminDuplicateReviewEntryResponse,
)
from app.services.typed_values import flatten_typed_values, materialize_typed_values


class AdminDuplicateService:
    """Review same-title candidates in the unified Catalog Item v1 catalog."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        actor_user_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> None:
        self.db = db
        self._actor_user_id = actor_user_id
        self._actor_email = actor_email

    async def duplicate_candidates(self, limit: int = 10) -> list[AdminDuplicateCandidateResponse]:
        count_expression = func.count(CanonicalCatalogItem.id)
        groups = await self.db.execute(
            select(CanonicalCatalogItem.kind, CanonicalCatalogItem.title, count_expression)
            .group_by(CanonicalCatalogItem.kind, CanonicalCatalogItem.title)
            .having(count_expression > 1)
            .order_by(
                count_expression.desc(),
                CanonicalCatalogItem.kind.asc(),
                CanonicalCatalogItem.title.asc(),
            )
            .limit(min(max(limit * 4, limit), 200))
        )
        candidates: list[AdminDuplicateCandidateResponse] = []
        for kind, title, count in groups.all():
            items = list(
                (
                    await self.db.scalars(
                        select(CanonicalCatalogItem)
                        .where(
                            CanonicalCatalogItem.kind == kind,
                            CanonicalCatalogItem.title == title,
                        )
                        .order_by(CanonicalCatalogItem.id.asc())
                    )
                ).all()
            )
            item_ids = [item.id for item in items]
            if await self._duplicate_group_is_ignored(item_ids):
                continue
            cover_signatures = {
                signature
                for item in items
                if (signature := self._cover_signature(item.details)) is not None
            }
            candidates.append(
                AdminDuplicateCandidateResponse(
                    kind=kind,
                    title=title,
                    item_number=None,
                    count=int(count),
                    item_ids=item_ids,
                    reason="same kind and title",
                    has_cover_conflicts=len(cover_signatures) > 1,
                    duplicate_score=100,
                )
            )
        candidates.sort(key=lambda row: (-row.count, row.kind, row.title.casefold()))
        return candidates[:limit]

    async def duplicate_group_count(self) -> int:
        return len(await self.duplicate_candidates(limit=200))

    async def ignore_duplicate_candidate(
        self,
        payload: AdminDuplicateIgnoreRequest,
    ) -> AdminDuplicateActionResponse:
        item_ids = list(dict.fromkeys(payload.item_ids))
        items = list(
            (
                await self.db.scalars(
                    select(CanonicalCatalogItem).where(CanonicalCatalogItem.id.in_(item_ids))
                )
            ).all()
        )
        by_id = {item.id: item for item in items}
        if len(by_id) != len(item_ids):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="duplicate_item_not_found",
                detail="One or more Catalog Items were not found.",
            )
        ordered_items = [by_id[item_id] for item_id in item_ids]
        if len({(item.kind, item.title) for item in ordered_items}) != 1:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_group_mismatch",
                detail="Catalog Items must have the same kind and title.",
            )

        ignore_token = self._ignore_token(item_ids)
        existing_id = await self.db.scalar(
            select(DuplicateReview.id).where(
                DuplicateReview.action == "ignore",
                DuplicateReview.ignore_token == ignore_token,
            )
        )
        if existing_id is not None:
            return AdminDuplicateActionResponse(ok=True, affected_items=len(item_ids))

        item_ids_json = [str(item_id) for item_id in item_ids]
        review = DuplicateReview(
            action="ignore",
            entity_type="catalog_item",
            entity_id=item_ids[0],
            ignore_token=ignore_token,
            duplicate_score=100,
            actor_user_id=self._actor_user_id,
            actor_email=self._actor_email,
        )
        review.entities = [
            DuplicateReviewEntity(
                role="candidate",
                entity_id=item_id,
                position=position,
            )
            for position, item_id in enumerate(item_ids)
        ]
        review_details = {
            "decision": "ignore",
            "item_ids": item_ids_json,
            "kind": ordered_items[0].kind,
            "title": ordered_items[0].title,
            "duplicate_score": 100,
        }
        review.details = [
            DuplicateReviewDetail(**row) for row in flatten_typed_values(review_details)
        ]

        audit = AdminAuditLog(
            action="duplicates.ignore",
            actor_user_id=self._actor_user_id,
            actor_email=self._actor_email,
            entity_type="catalog_item",
            entity_id=item_ids[0],
        )
        audit.details = [AdminAuditLogDetail(**row) for row in flatten_typed_values(review_details)]
        self.db.add_all([review, audit])
        await self.db.commit()
        return AdminDuplicateActionResponse(ok=True, affected_items=len(item_ids))

    async def duplicate_queue_summary(self) -> AdminDuplicateQueueSummaryResponse:
        review_rows = await self.db.execute(
            select(DuplicateReview.action, func.count(DuplicateReview.id)).group_by(
                DuplicateReview.action
            )
        )
        counts = dict(review_rows.all())
        latest_review_at = await self.db.scalar(select(func.max(DuplicateReview.created_at)))
        return AdminDuplicateQueueSummaryResponse(
            pending_candidates=await self.duplicate_group_count(),
            merged_reviews=int(counts.get("merge", 0) or 0),
            ignored_reviews=int(counts.get("ignore", 0) or 0),
            total_reviews=sum(int(value or 0) for value in counts.values()),
            latest_review_at=latest_review_at,
        )

    async def duplicate_review_history(
        self, limit: int = 25
    ) -> list[AdminDuplicateReviewEntryResponse]:
        result = await self.db.execute(
            select(DuplicateReview)
            .options(
                selectinload(DuplicateReview.entities),
                selectinload(DuplicateReview.details),
            )
            .order_by(DuplicateReview.created_at.desc(), DuplicateReview.id.desc())
            .limit(limit)
        )
        responses: list[AdminDuplicateReviewEntryResponse] = []
        for review in result.scalars():
            response = AdminDuplicateReviewEntryResponse.model_validate(review)
            entity_ids = [str(entity.entity_id) for entity in review.entities]
            source_entity_ids = [
                str(entity.entity_id) for entity in review.entities if entity.role == "source"
            ]
            responses.append(
                response.model_copy(
                    update={
                        "entity_ids": entity_ids,
                        "source_entity_ids": source_entity_ids or None,
                        "details_json": materialize_typed_values(review.details),
                    }
                )
            )
        return responses

    async def _duplicate_group_is_ignored(self, item_ids: list[UUID]) -> bool:
        existing_id = await self.db.scalar(
            select(DuplicateReview.id).where(
                DuplicateReview.action == "ignore",
                DuplicateReview.ignore_token == self._ignore_token(item_ids),
            )
        )
        return existing_id is not None

    @staticmethod
    def _ignore_token(item_ids: list[UUID]) -> str:
        return "|".join(sorted(str(item_id) for item_id in item_ids))

    @staticmethod
    def _cover_signature(details: dict[str, Any]) -> str | None:
        direct = details.get("cover_image_url")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        images = details.get("images")
        if not isinstance(images, list):
            return None
        for image in images:
            if not isinstance(image, dict):
                continue
            if image.get("image_type") not in {"front_cover", "cover", "poster"}:
                continue
            value = image.get("url") or image.get("image_key")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
