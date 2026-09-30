from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ApiHTTPException
from app.models import (
    AnimeSeries,
    BoardGameWork,
    BookWork,
    ComicWork,
    DuplicateReview,
    DuplicateReviewDetail,
    DuplicateReviewEntity,
    GameWork,
    MangaWork,
    MovieWork,
    MusicItem,
    TVSeries,
)
from app.schemas.admin import (
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateQueueSummaryResponse,
    AdminDuplicateReviewEntryResponse,
)
from app.services.typed_values import flatten_typed_values, materialize_typed_values

# Maps each native root model class to the entity_type string used in generic link tables.
_ENTITY_TYPE: dict[type, str] = {
    BookWork: "book_work",
    ComicWork: "comic_work",
    MangaWork: "manga_work",
    AnimeSeries: "anime_series",
    MovieWork: "movie_work",
    TVSeries: "tv_series",
    GameWork: "game_work",
    BoardGameWork: "boardgame_work",
    MusicItem: "catalog_music_item",
}

# Maps each native root model class to a human-readable kind label.
_KIND_LABEL: dict[type, str] = {
    BookWork: "book",
    ComicWork: "comic",
    MangaWork: "manga",
    AnimeSeries: "anime",
    MovieWork: "movie",
    TVSeries: "tv",
    GameWork: "game",
    BoardGameWork: "boardgame",
    MusicItem: "music",
}

# All native root model classes in scan order.
_NATIVE_MODELS: list[type] = list(_ENTITY_TYPE.keys())


class AdminDuplicateService:
    def __init__(
        self,
        db: AsyncSession,
        audit_recorder: Callable[..., None],
        character_role_rank: Callable[[str], int],
        *,
        actor_user_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> None:
        self.db = db
        self._audit_recorder = audit_recorder
        self._character_role_rank = character_role_rank
        self._actor_user_id = actor_user_id
        self._actor_email = actor_email

    async def duplicate_candidates(self, limit: int = 10) -> list[AdminDuplicateCandidateResponse]:
        raw_groups: list[tuple[type, str, int, list[UUID]]] = []
        per_model_limit = min(limit * 4, 200)
        for model_cls in _NATIVE_MODELS:
            count_label = func.count(model_cls.id).label("count")
            ids_label = func.array_agg(model_cls.id).label("ids")
            result = await self.db.execute(
                select(model_cls.title, count_label, ids_label)
                .group_by(model_cls.title)
                .having(func.count(model_cls.id) > 1)
                .order_by(count_label.desc(), model_cls.title.asc())
                .limit(per_model_limit)
            )
            for title, count, ids in result.all():
                raw_groups.append((model_cls, title, count, list(ids or [])))

        candidates: list[AdminDuplicateCandidateResponse] = []
        for model_cls, title, count, entity_ids in raw_groups:
            entity_type = _ENTITY_TYPE[model_cls]
            kind_label = _KIND_LABEL[model_cls]
            if await self._duplicate_group_is_ignored(entity_ids, model_cls):
                continue
            conflicts = await self._duplicate_conflict_flags(entity_ids)
            entities = await self._entities_by_ids(entity_ids, model_cls)
            duplicate_score, recommended_target_id = self._score_duplicate_candidate(
                entities,
                conflicts=conflicts,
            )
            confidence_factors = self._duplicate_confidence_factors(
                entities,
                conflicts=conflicts,
            )
            merge_warnings = self._duplicate_merge_warnings(conflicts)
            candidates.append(
                AdminDuplicateCandidateResponse(
                    kind=kind_label,
                    title=title,
                    item_number=None,
                    count=count,
                    item_ids=entity_ids,
                    reason="same title",
                    has_cover_conflicts=conflicts["cover"],
                    duplicate_score=duplicate_score,
                    recommended_target_item_id=recommended_target_id,
                    confidence_factors=confidence_factors,
                    merge_warnings=merge_warnings,
                )
            )
        candidates.sort(
            key=lambda c: (-c.duplicate_score, -c.count, c.title.lower())
        )
        return candidates[:limit]

    async def duplicate_queue_summary(self) -> AdminDuplicateQueueSummaryResponse:
        pending_candidates = await self.duplicate_group_count()
        review_rows = await self.db.execute(
            select(
                DuplicateReview.action,
                func.count(DuplicateReview.id),
            ).group_by(DuplicateReview.action)
        )
        counts = dict(review_rows.all())
        latest_review_at = await self.db.scalar(select(func.max(DuplicateReview.created_at)))
        return AdminDuplicateQueueSummaryResponse(
            pending_candidates=pending_candidates,
            merged_reviews=int(counts.get("merge", 0) or 0),
            ignored_reviews=int(counts.get("ignore", 0) or 0),
            total_reviews=sum(int(value or 0) for value in counts.values()),
            latest_review_at=latest_review_at,
        )

    async def duplicate_review_history(
        self,
        limit: int = 25,
    ) -> list[AdminDuplicateReviewEntryResponse]:
        stmt = (
            select(DuplicateReview)
            .order_by(DuplicateReview.created_at.desc(), DuplicateReview.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(
            stmt.options(
                selectinload(DuplicateReview.entities),
                selectinload(DuplicateReview.details),
            )
        )
        responses: list[AdminDuplicateReviewEntryResponse] = []
        for row in result.scalars():
            response = AdminDuplicateReviewEntryResponse.model_validate(row)
            entity_ids = [str(entry.entity_id) for entry in row.entities]
            source_entity_ids = [
                str(entry.entity_id) for entry in row.entities if entry.role == "source"
            ]
            responses.append(
                response.model_copy(
                    update={
                        "entity_ids": entity_ids,
                        "source_entity_ids": source_entity_ids or None,
                        "details_json": materialize_typed_values(row.details),
                    }
                )
            )
        return responses

    async def ignore_duplicate_candidate(
        self,
        payload: AdminDuplicateIgnoreRequest,
        *,
        note: str | None = None,
    ) -> AdminDuplicateActionResponse:
        entities = await self._entities_by_ids(payload.item_ids)
        if len(entities) != len(set(payload.item_ids)):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="duplicate_item_not_found",
                detail="One or more duplicate items were not found",
            )
        self._ensure_same_duplicate_group(entities)
        entity_type = _ENTITY_TYPE[type(entities[0])]
        ids = [e.id for e in entities]
        token = self._duplicate_ignore_token(ids)
        conflicts = await self._duplicate_conflict_flags(ids)
        confidence_factors = self._duplicate_confidence_factors(entities, conflicts=conflicts)
        merge_warnings = self._duplicate_merge_warnings(conflicts)
        duplicate_score, recommended_target_id = self._score_duplicate_candidate(
            entities, conflicts=conflicts
        )
        review = DuplicateReview(
                action="ignore",
                entity_type=entity_type,
                entity_id=ids[0],
                ignore_token=token,
                duplicate_score=duplicate_score,
                actor_user_id=self._actor_user_id,
                actor_email=self._actor_email,
                note=note,
            )
        review.entities = [
            DuplicateReviewEntity(role="candidate", entity_id=entity_id, position=index)
            for index, entity_id in enumerate(ids)
        ]
        review.details = [
            DuplicateReviewDetail(**detail)
            for detail in flatten_typed_values(
                {
                    "decision": "ignore",
                    "item_ids": [str(entity_id) for entity_id in ids],
                    "duplicate_score": duplicate_score,
                    "recommended_target_item_id": str(recommended_target_id) if recommended_target_id else None,
                    "confidence_factors": confidence_factors,
                    "merge_warnings": merge_warnings,
                    **({"note": note} if note else {}),
                }
            )
        ]
        self.db.add(review)
        self._record_duplicate_review_audit(
            action="duplicates.ignore",
            entities=entities,
            duplicate_score=duplicate_score,
            recommended_target_id=recommended_target_id,
            confidence_factors=confidence_factors,
            merge_warnings=merge_warnings,
            details={"decision": "ignore", **({"note": note} if note else {})},
        )
        await self.db.commit()
        return AdminDuplicateActionResponse(ok=True, affected_items=len(entities))

    async def duplicate_group_count(self) -> int:
        return len(await self.duplicate_candidates(limit=200))

    # ------------------------------------------------------------------ #
    # Private helpers â€” entity loading                                     #
    # ------------------------------------------------------------------ #

    async def _entities_by_ids(
        self,
        entity_ids: list[UUID],
        model_cls: type | None = None,
    ) -> list[Any]:
        """Load native root model instances by UUID.

        When *model_cls* is provided the search is restricted to that table.
        Otherwise all native root model tables are probed in order; the first
        table that returns results is assumed to own the entire batch.
        """
        unique_ids = list(dict.fromkeys(entity_ids))
        candidates_cls = [model_cls] if model_cls is not None else _NATIVE_MODELS
        for cls in candidates_cls:
            result = await self.db.execute(select(cls).where(cls.id.in_(unique_ids)))
            found = list(result.scalars().unique())
            if found:
                by_id = {e.id: e for e in found}
                return [by_id[eid] for eid in unique_ids if eid in by_id]
        return []

    def _ensure_same_duplicate_group(self, entities: list[Any]) -> None:
        if len(entities) < 2:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_action_requires_multiple_items",
                detail="Duplicate action requires at least two items",
            )
        first = entities[0]
        model_cls = type(first)
        title = first.title
        if any(type(e) is not model_cls or e.title != title for e in entities[1:]):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_group_mismatch",
                detail="Duplicate action items must belong to the same candidate group",
            )

    async def _duplicate_group_is_ignored(
        self, entity_ids: list[UUID], model_cls: type
    ) -> bool:
        if len(entity_ids) < 2:
            return False
        token = self._duplicate_ignore_token(entity_ids)
        stored = await self.db.scalar(
            select(DuplicateReview.id).where(
                DuplicateReview.action == "ignore",
                DuplicateReview.ignore_token == token,
            )
        )
        if stored is not None:
            return True
        return False

    # ------------------------------------------------------------------ #
    # Private helpers â€” conflict detection & scoring                       #
    # ------------------------------------------------------------------ #

    async def _duplicate_conflict_flags(self, entity_ids: list[UUID]) -> dict[str, bool]:
        # Cover conflict: check model-level cover fields (not all models have them)
        entities = await self._entities_by_ids(entity_ids)
        cover_sigs: set[tuple[str | None, str | None]] = set()
        for e in entities:
            url = getattr(e, "cover_image_url", None) or getattr(e, "poster_image_url", None)
            key = getattr(e, "cover_image_key", None) or getattr(e, "poster_image_key", None)
            if url or key:
                cover_sigs.add((url, key))

        return {"cover": len(cover_sigs) > 1}

    def _score_duplicate_candidate(
        self,
        entities: list[Any],
        *,
        conflicts: dict[str, bool],
    ) -> tuple[int, UUID | None]:
        if len(entities) < 2:
            return 0, None
        score = 55
        if not conflicts["cover"]:
            score += 8
        if self._entities_share_publisher(entities):
            score += 6
        if self._entities_share_release_marker(entities):
            score += 5
        recommended_target_id = max(
            entities,
            key=self._merge_target_score,
        ).id
        return min(score, 99), recommended_target_id

    def _duplicate_confidence_factors(
        self,
        entities: list[Any],
        *,
        conflicts: dict[str, bool],
    ) -> list[str]:
        if len(entities) < 2:
            return []
        factors: list[str] = []
        if not conflicts["cover"]:
            factors.append("cover_images_consistent")
        if self._entities_share_publisher(entities):
            factors.append("publisher_aligned")
        if self._entities_share_release_marker(entities):
            factors.append("release_markers_aligned")
        return factors

    def _duplicate_merge_warnings(self, conflicts: dict[str, bool]) -> list[str]:
        warnings: list[str] = []
        if conflicts["cover"]:
            warnings.append("cover_asset_conflict")
        return warnings
    def _merge_target_score(self, entity: Any) -> tuple[int, int]:
        # Count immediate child collections as a proxy for "richness"
        child_count = 0
        for attr in ("editions", "releases", "issues", "chapters", "episodes", "media", "discs"):
            children = getattr(entity, attr, None)
            if isinstance(children, list):
                child_count += len(children)
        score = 0
        if self._entity_has_cover(entity):
            score += 14
        if self._entity_release_marker(entity) is not None:
            score += 8
        if self._entity_primary_publisher(entity) is not None:
            score += 6
        score += child_count * 3
        return score, child_count

    def _entities_share_publisher(self, entities: list[Any]) -> bool:
        publishers = [self._entity_primary_publisher(e) for e in entities]
        return all(p is not None for p in publishers) and len(set(publishers)) == 1

    def _entities_share_release_marker(self, entities: list[Any]) -> bool:
        markers = [self._entity_release_marker(e) for e in entities]
        return all(m is not None for m in markers) and len(set(markers)) == 1

    def _entity_has_cover(self, entity: Any) -> bool:
        for attr in ("cover_image_url", "cover_image_key", "poster_image_url", "poster_image_key"):
            if getattr(entity, attr, None):
                return True
        return False

    def _entity_primary_publisher(self, entity: Any) -> str | None:
        studios = getattr(entity, "studios", None)
        studio = getattr(entity, "studio", None)
        if studio is None and isinstance(studios, list) and studios:
            studio = studios[0]
        pub = getattr(entity, "publisher", None) or studio
        if pub and str(pub).strip():
            return str(pub).strip().lower()
        return None

    def _entity_release_marker(self, entity: Any) -> str | None:
        for attr in (
            "release_date",
            "original_release_date",
            "original_publication_date",
            "first_publication_date",
            "original_air_date",
        ):
            val = getattr(entity, attr, None)
            if val is not None:
                return str(val)
        return None

    def _duplicate_ignore_token(self, entity_ids: list[UUID]) -> str:
        return "|".join(sorted(str(eid) for eid in entity_ids))

    # ------------------------------------------------------------------ #
    # Private helpers â€” merge / child reassignment                         #
    # ------------------------------------------------------------------ #

    def _record_duplicate_review_audit(
        self,
        *,
        action: str,
        entities: list[Any],
        duplicate_score: int,
        recommended_target_id: UUID | None,
        confidence_factors: list[str],
        merge_warnings: list[str],
        details: dict[str, Any],
        entity_id: UUID | None = None,
    ) -> None:
        model_cls = type(entities[0]) if entities else None
        self._audit_recorder(
            action=action,
            entity_type="duplicate_group" if entity_id is None else "item",
            entity_id=entity_id,
            details={
                "item_ids": [e.id for e in entities],
                "kind": _KIND_LABEL.get(model_cls) if model_cls else None,
                "title": entities[0].title if entities else None,
                "item_number": None,
                "duplicate_score": duplicate_score,
                "recommended_target_item_id": recommended_target_id,
                "confidence_factors": confidence_factors,
                "merge_warnings": merge_warnings,
                **details,
            },
        )
