from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiHTTPException
from app.models import (
    AnimeCharacterAppearance,
    AnimeContribution,
    AnimeEpisode,
    AnimeIdentifier,
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookSeriesMembership,
    BookWork,
    ComicContribution,
    ComicIssue,
    ComicSeriesMembership,
    ComicWork,
    DuplicateReview,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    GameRelease,
    GameWork,
    ImageAsset,
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaIdentifier,
    MangaSeriesMembership,
    MangaWork,
    MovieRelease,
    MovieWork,
    MovieWorkContribution,
    MovieWorkIdentifier,
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseIdentifier,
    MusicTrack,
    TVEpisode,
    TVRelease,
    TVReleaseContribution,
    TVReleaseIdentifier,
    TVReleaseMedia,
)
from app.schemas.admin import (
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
    AdminDuplicateReviewRequest,
)

# Maps each native root model class to the entity_type string used in generic link tables.
_ENTITY_TYPE: dict[type, str] = {
    BookWork: "book_work",
    ComicWork: "comic_work",
    MangaWork: "manga_work",
    AnimeSeries: "anime_series",
    MovieWork: "movie_work",
    TVRelease: "tv_release",
    GameWork: "game_work",
    BoardGameWork: "boardgame_work",
    MusicRelease: "music_release",
}

# Maps each native root model class to a human-readable kind label.
_KIND_LABEL: dict[type, str] = {
    BookWork: "book",
    ComicWork: "comic",
    MangaWork: "manga",
    AnimeSeries: "anime",
    MovieWork: "movie",
    TVRelease: "tv",
    GameWork: "game",
    BoardGameWork: "boardgame",
    MusicRelease: "music",
}

# All native root model classes in scan order.
_NATIVE_MODELS: list[type] = list(_ENTITY_TYPE.keys())


class AdminDuplicateService:
    def __init__(
        self,
        db: AsyncSession,
        item_response_loader: Callable[[Any], Awaitable[Any]],
        audit_recorder: Callable[..., None],
        character_role_rank: Callable[[str], int],
        *,
        actor_user_id: UUID | None = None,
        actor_email: str | None = None,
    ) -> None:
        self.db = db
        self._item_response_loader = item_response_loader
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
            conflicts = await self._duplicate_conflict_flags(entity_ids, entity_type)
            entities = await self._entities_by_ids(entity_ids, model_cls)
            provider_counts = await self._provider_link_counts(entity_ids, entity_type)
            duplicate_score, recommended_target_id = self._score_duplicate_candidate(
                entities,
                provider_counts,
                conflicts=conflicts,
            )
            confidence_factors = self._duplicate_confidence_factors(
                entities,
                provider_counts,
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
                    has_provider_conflicts=conflicts["provider"],
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
        conflicts = await self._duplicate_conflict_flags(ids, entity_type)
        provider_counts = await self._provider_link_counts(ids, entity_type)
        confidence_factors = self._duplicate_confidence_factors(entities, provider_counts, conflicts=conflicts)
        merge_warnings = self._duplicate_merge_warnings(conflicts)
        duplicate_score, recommended_target_id = self._score_duplicate_candidate(
            entities, provider_counts, conflicts=conflicts
        )
        for entity in entities:
            metadata = dict(entity.metadata_json or {})
            metadata["admin_duplicate_ignore_token"] = token
            metadata["admin_duplicate_ignored_at"] = datetime.now(UTC).isoformat()
            entity.metadata_json = metadata
        self.db.add(
            DuplicateReview(
                action="ignore",
                entity_type=entity_type,
                entity_id=ids[0],
                entity_ids=[str(entity_id) for entity_id in ids],
                ignore_token=token,
                duplicate_score=duplicate_score,
                actor_user_id=self._actor_user_id,
                actor_email=self._actor_email,
                note=note,
                details_json={
                    "decision": "ignore",
                    "item_ids": [str(entity_id) for entity_id in ids],
                    "duplicate_score": duplicate_score,
                    "recommended_target_item_id": str(recommended_target_id) if recommended_target_id else None,
                    "confidence_factors": confidence_factors,
                    "merge_warnings": merge_warnings,
                    **({"note": note} if note else {}),
                },
            )
        )
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

    async def merge_duplicate_candidate(
        self,
        payload: AdminDuplicateMergeRequest,
        *,
        note: str | None = None,
    ) -> AdminDuplicateActionResponse:
        source_ids = [eid for eid in payload.source_item_ids if eid != payload.target_item_id]
        if not source_ids:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_source_required",
                detail="At least one source item different from target_item_id is required",
            )
        entities = await self._entities_by_ids([payload.target_item_id, *source_ids])
        if len(entities) != len({payload.target_item_id, *source_ids}):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="duplicate_item_not_found",
                detail="One or more duplicate items were not found",
            )
        target = next(e for e in entities if e.id == payload.target_item_id)
        sources = [e for e in entities if e.id != payload.target_item_id]
        self._ensure_same_duplicate_group([target, *sources])
        entity_type = _ENTITY_TYPE[type(target)]
        all_ids = [e.id for e in [target, *sources]]
        conflicts = await self._duplicate_conflict_flags(all_ids, entity_type)
        provider_counts = await self._provider_link_counts(all_ids, entity_type)
        confidence_factors = self._duplicate_confidence_factors(
            [target, *sources], provider_counts, conflicts=conflicts
        )
        merge_warnings = self._duplicate_merge_warnings(conflicts)
        duplicate_score, recommended_target_id = self._score_duplicate_candidate(
            [target, *sources], provider_counts, conflicts=conflicts
        )

        for source in sources:
            await self._move_entity_children(source, target)
            await self.db.delete(source)
        self.db.add(
            DuplicateReview(
                action="merge",
                entity_type=entity_type,
                entity_id=target.id,
                entity_ids=[str(entity_id) for entity_id in all_ids],
                target_entity_id=target.id,
                source_entity_ids=[str(source.id) for source in sources],
                duplicate_score=duplicate_score,
                actor_user_id=self._actor_user_id,
                actor_email=self._actor_email,
                note=note,
                details_json={
                    "decision": "merge",
                    "target_item_id": str(target.id),
                    "source_item_ids": [str(source.id) for source in sources],
                    "duplicate_score": duplicate_score,
                    "recommended_target_item_id": str(recommended_target_id) if recommended_target_id else None,
                    "confidence_factors": confidence_factors,
                    "merge_warnings": merge_warnings,
                    **({"note": note} if note else {}),
                },
            )
        )
        self._record_duplicate_review_audit(
            action="duplicates.merge",
            entities=[target, *sources],
            entity_id=target.id,
            duplicate_score=duplicate_score,
            recommended_target_id=recommended_target_id,
            confidence_factors=confidence_factors,
            merge_warnings=merge_warnings,
            details={
                "decision": "merge",
                "target_item_id": target.id,
                "source_item_ids": [s.id for s in sources],
                **({"note": note} if note else {}),
            },
        )
        await self.db.commit()
        response_item = await self._item_response_loader(target)
        return AdminDuplicateActionResponse(
            ok=True,
            affected_items=len(sources),
            item=response_item,
        )

    async def review_duplicate_candidate(
        self,
        payload: AdminDuplicateReviewRequest,
    ) -> AdminDuplicateActionResponse:
        if payload.decision == "ignore":
            if not payload.item_ids:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="duplicate_item_ids_required",
                    detail="item_ids are required when decision is ignore",
                )
            return await self.ignore_duplicate_candidate(
                AdminDuplicateIgnoreRequest(item_ids=payload.item_ids),
                note=payload.note,
            )
        if payload.target_item_id is None or not payload.source_item_ids:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_merge_payload_invalid",
                detail="target_item_id and source_item_ids are required when decision is merge",
            )
        return await self.merge_duplicate_candidate(
            AdminDuplicateMergeRequest(
                target_item_id=payload.target_item_id,
                source_item_ids=payload.source_item_ids,
            ),
            note=payload.note,
        )

    async def duplicate_group_count(self) -> int:
        return len(await self.duplicate_candidates(limit=200))

    # ------------------------------------------------------------------ #
    # Private helpers — entity loading                                     #
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
        result = await self.db.execute(
            select(model_cls.metadata_json).where(model_cls.id.in_(entity_ids))
        )
        rows = list(result.scalars())
        if len(rows) != len(entity_ids):
            return False
        return all(
            isinstance(m, dict) and m.get("admin_duplicate_ignore_token") == token
            for m in rows
        )

    # ------------------------------------------------------------------ #
    # Private helpers — conflict detection & scoring                       #
    # ------------------------------------------------------------------ #

    async def _duplicate_conflict_flags(
        self, entity_ids: list[UUID], entity_type: str
    ) -> dict[str, bool]:
        provider_result = await self.db.execute(
            select(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
            .where(
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.entity_id.in_(entity_ids),
            )
            .order_by(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
        )
        provider_ids_by_provider: dict[str, set[str]] = {}
        for provider, pid in provider_result.all():
            provider_ids_by_provider.setdefault(str(provider), set()).add(pid)
        has_provider_conflicts = any(len(v) > 1 for v in provider_ids_by_provider.values())

        # Cover conflict: check model-level cover fields (not all models have them)
        entities = await self._entities_by_ids(entity_ids)
        cover_sigs: set[tuple[str | None, str | None]] = set()
        for e in entities:
            url = getattr(e, "cover_image_url", None) or getattr(e, "poster_image_url", None)
            key = getattr(e, "cover_image_key", None) or getattr(e, "poster_image_key", None)
            if url or key:
                cover_sigs.add((url, key))

        return {
            "provider": has_provider_conflicts,
            "cover": len(cover_sigs) > 1,
        }

    def _score_duplicate_candidate(
        self,
        entities: list[Any],
        provider_counts: dict[UUID, int],
        *,
        conflicts: dict[str, bool],
    ) -> tuple[int, UUID | None]:
        if len(entities) < 2:
            return 0, None
        score = 55
        if not conflicts["provider"]:
            score += 12
        if not conflicts["cover"]:
            score += 8
        if provider_counts:
            score += 6
        if len(provider_counts) == len(entities):
            score += 4
        if self._entities_share_publisher(entities):
            score += 6
        if self._entities_share_release_marker(entities):
            score += 5
        recommended_target_id = max(
            entities,
            key=lambda e: self._merge_target_score(e, provider_counts.get(e.id, 0)),
        ).id
        return min(score, 99), recommended_target_id

    def _duplicate_confidence_factors(
        self,
        entities: list[Any],
        provider_counts: dict[UUID, int],
        *,
        conflicts: dict[str, bool],
    ) -> list[str]:
        if len(entities) < 2:
            return []
        factors: list[str] = []
        if not conflicts["provider"]:
            factors.append("provider_ids_consistent")
        if not conflicts["cover"]:
            factors.append("cover_images_consistent")
        if provider_counts:
            factors.append("provider_links_present")
        if len(provider_counts) == len(entities):
            factors.append("provider_links_present_for_all_items")
        if self._entities_share_publisher(entities):
            factors.append("publisher_aligned")
        if self._entities_share_release_marker(entities):
            factors.append("release_markers_aligned")
        return factors

    def _duplicate_merge_warnings(self, conflicts: dict[str, bool]) -> list[str]:
        warnings: list[str] = []
        if conflicts["provider"]:
            warnings.append("provider_id_conflict")
        if conflicts["cover"]:
            warnings.append("cover_asset_conflict")
        return warnings

    async def _provider_link_counts(
        self, entity_ids: list[UUID], entity_type: str
    ) -> dict[UUID, int]:
        result = await self.db.execute(
            select(ExternalProviderId.entity_id, func.count(ExternalProviderId.id))
            .where(
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.entity_id.in_(entity_ids),
            )
            .group_by(ExternalProviderId.entity_id)
        )
        return dict(result.all())

    def _merge_target_score(self, entity: Any, provider_link_count: int) -> tuple[int, int, int]:
        # Count immediate child collections as a proxy for "richness"
        child_count = 0
        for attr in ("editions", "releases", "issues", "chapters", "episodes", "media"):
            children = getattr(entity, attr, None)
            if isinstance(children, list):
                child_count += len(children)
        score = provider_link_count * 25
        if self._entity_has_cover(entity):
            score += 14
        if self._entity_release_marker(entity) is not None:
            score += 8
        if self._entity_primary_publisher(entity) is not None:
            score += 6
        score += child_count * 3
        return score, provider_link_count, child_count

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
        pub = getattr(entity, "publisher", None) or getattr(entity, "studio", None)
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
    # Private helpers — merge / child reassignment                         #
    # ------------------------------------------------------------------ #

    async def _move_entity_children(self, source: Any, target: Any) -> None:
        """Reassign all children and generic links from *source* to *target*."""
        entity_type = _ENTITY_TYPE[type(source)]

        await self._move_native_children(source, target)
        await self._move_provider_links(entity_type, source.id, target.id)
        await self._move_organization_links(entity_type, source.id, target.id)
        await self._move_person_links(entity_type, source.id, target.id)
        await self._move_tag_links(entity_type, source.id, target.id)
        await self.db.execute(
            update(ImageAsset)
            .where(ImageAsset.entity_type == entity_type, ImageAsset.entity_id == source.id)
            .values(entity_id=target.id)
        )
        # Merge metadata_json: target values win; source fills in missing keys.
        if source.metadata_json:
            merged = {**dict(source.metadata_json), **dict(target.metadata_json or {})}
            target.metadata_json = merged

    async def _move_native_children(self, source: Any, target: Any) -> None:
        """Per-model child-row reassignment via bulk UPDATE statements."""
        sid, tid = source.id, target.id

        if isinstance(source, BookWork):
            await self.db.execute(update(BookEdition).where(BookEdition.work_id == sid).values(work_id=tid))
            await self.db.execute(
                update(BookContribution)
                .where(BookContribution.work_id == sid)
                .values(work_id=tid)
            )
            await self.db.execute(
                update(BookSeriesMembership)
                .where(BookSeriesMembership.work_id == sid)
                .values(work_id=tid)
            )

        elif isinstance(source, ComicWork):
            await self.db.execute(update(ComicIssue).where(ComicIssue.work_id == sid).values(work_id=tid))
            await self.db.execute(
                update(ComicContribution)
                .where(ComicContribution.work_id == sid)
                .values(work_id=tid)
            )
            await self.db.execute(
                update(ComicSeriesMembership)
                .where(ComicSeriesMembership.work_id == sid)
                .values(work_id=tid)
            )

        elif isinstance(source, MangaWork):
            await self.db.execute(update(MangaChapter).where(MangaChapter.work_id == sid).values(work_id=tid))
            await self.db.execute(
                update(MangaContribution)
                .where(MangaContribution.work_id == sid)
                .values(work_id=tid)
            )
            await self.db.execute(update(MangaIdentifier).where(MangaIdentifier.work_id == sid).values(work_id=tid))
            await self.db.execute(
                update(MangaCharacterAppearance)
                .where(MangaCharacterAppearance.work_id == sid)
                .values(work_id=tid)
            )
            await self.db.execute(
                update(MangaSeriesMembership)
                .where(MangaSeriesMembership.work_id == sid)
                .values(work_id=tid)
            )

        elif isinstance(source, AnimeSeries):
            await self.db.execute(update(AnimeEpisode).where(AnimeEpisode.series_id == sid).values(series_id=tid))
            await self.db.execute(
                update(AnimeContribution)
                .where(AnimeContribution.series_id == sid)
                .values(series_id=tid)
            )
            await self.db.execute(update(AnimeIdentifier).where(AnimeIdentifier.series_id == sid).values(series_id=tid))
            await self.db.execute(
                update(AnimeCharacterAppearance)
                .where(AnimeCharacterAppearance.series_id == sid)
                .values(series_id=tid)
            )

        elif isinstance(source, MovieWork):
            await self.db.execute(update(MovieRelease).where(MovieRelease.work_id == sid).values(work_id=tid))
            await self.db.execute(
                update(MovieWorkContribution)
                .where(MovieWorkContribution.work_id == sid)
                .values(work_id=tid)
            )
            await self.db.execute(
                update(MovieWorkIdentifier)
                .where(MovieWorkIdentifier.work_id == sid)
                .values(work_id=tid)
            )

        elif isinstance(source, TVRelease):
            await self.db.execute(update(TVReleaseMedia).where(TVReleaseMedia.release_id == sid).values(release_id=tid))
            await self.db.execute(update(TVEpisode).where(TVEpisode.release_id == sid).values(release_id=tid))
            await self.db.execute(
                update(TVReleaseContribution)
                .where(TVReleaseContribution.release_id == sid)
                .values(release_id=tid)
            )
            await self.db.execute(
                update(TVReleaseIdentifier)
                .where(TVReleaseIdentifier.release_id == sid)
                .values(release_id=tid)
            )

        elif isinstance(source, GameWork):
            await self.db.execute(update(GameRelease).where(GameRelease.work_id == sid).values(work_id=tid))

        elif isinstance(source, BoardGameWork):
            await self.db.execute(update(BoardGameEdition).where(BoardGameEdition.work_id == sid).values(work_id=tid))

        elif isinstance(source, MusicRelease):
            await self.db.execute(update(MusicMedia).where(MusicMedia.release_id == sid).values(release_id=tid))
            await self.db.execute(update(MusicTrack).where(MusicTrack.release_id == sid).values(release_id=tid))
            await self.db.execute(
                update(MusicReleaseContribution)
                .where(MusicReleaseContribution.release_id == sid)
                .values(release_id=tid)
            )
            await self.db.execute(
                update(MusicReleaseIdentifier)
                .where(MusicReleaseIdentifier.release_id == sid)
                .values(release_id=tid)
            )

    async def _move_provider_links(
        self, entity_type: str, source_id: UUID, target_id: UUID
    ) -> None:
        links = await self.db.scalars(
            select(ExternalProviderId).where(
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.entity_id == source_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(ExternalProviderId.id).where(
                    ExternalProviderId.entity_type == entity_type,
                    ExternalProviderId.entity_id == target_id,
                    ExternalProviderId.provider == link.provider,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_id

    async def _move_organization_links(
        self, entity_type: str, source_id: UUID, target_id: UUID
    ) -> None:
        links = await self.db.scalars(
            select(EntityOrganization).where(
                EntityOrganization.entity_type == entity_type,
                EntityOrganization.entity_id == source_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityOrganization.id).where(
                    EntityOrganization.entity_type == entity_type,
                    EntityOrganization.entity_id == target_id,
                    EntityOrganization.organization_id == link.organization_id,
                    EntityOrganization.role == link.role,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_id

    async def _move_person_links(
        self, entity_type: str, source_id: UUID, target_id: UUID
    ) -> None:
        links = await self.db.scalars(
            select(EntityPerson).where(
                EntityPerson.entity_type == entity_type,
                EntityPerson.entity_id == source_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityPerson.id).where(
                    EntityPerson.entity_type == entity_type,
                    EntityPerson.entity_id == target_id,
                    EntityPerson.person_id == link.person_id,
                    EntityPerson.role == link.role,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_id

    async def _move_tag_links(
        self, entity_type: str, source_id: UUID, target_id: UUID
    ) -> None:
        links = await self.db.scalars(
            select(EntityTag).where(
                EntityTag.entity_type == entity_type,
                EntityTag.entity_id == source_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityTag.id).where(
                    EntityTag.entity_type == entity_type,
                    EntityTag.entity_id == target_id,
                    EntityTag.tag_id == link.tag_id,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_id

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