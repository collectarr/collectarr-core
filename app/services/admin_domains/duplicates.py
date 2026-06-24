from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ApiHTTPException
from app.metadata_normalized import item_kind_metadata_payload, upsert_item_kind_metadata
from app.models.canonical import (
    CharacterAppearance,
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ImageAsset,
    Item,
    ItemProviderLink,
    StoryArcItem,
    Variant,
    Volume,
)
from app.repositories.metadata import MetadataRepository
from app.schemas.admin import (
    AdminDuplicateActionResponse,
    AdminDuplicateCandidateResponse,
    AdminDuplicateIgnoreRequest,
    AdminDuplicateMergeRequest,
)


class AdminDuplicateService:
    def __init__(
        self,
        db: AsyncSession,
        item_response_loader: Callable[[Item], Awaitable[Any]],
        audit_recorder: Callable[..., None],
        character_role_rank: Callable[[str], int],
    ) -> None:
        self.db = db
        self._item_response_loader = item_response_loader
        self._audit_recorder = audit_recorder
        self._character_role_rank = character_role_rank

    async def duplicate_candidates(self, limit: int = 10) -> list[AdminDuplicateCandidateResponse]:
        count_label = func.count(Item.id).label("count")
        item_ids_label = func.array_agg(Item.id).label("item_ids")
        result = await self.db.execute(
            select(
                Item.kind,
                Item.title,
                Item.item_number,
                count_label,
                item_ids_label,
            )
            .group_by(Item.kind, Item.title, Item.item_number)
            .having(func.count(Item.id) > 1)
            .order_by(count_label.desc(), Item.title.asc())
            .limit(min(limit * 4, 200))
        )
        candidates: list[AdminDuplicateCandidateResponse] = []
        for kind, title, item_number, count, item_ids in result.all():
            ids = list(item_ids or [])
            if await self._duplicate_group_is_ignored(ids):
                continue
            conflicts = await self._duplicate_conflict_flags(ids)
            items = await self._items_by_ids(ids)
            provider_counts = await self._provider_link_counts_by_item(ids)
            duplicate_score, recommended_target_item_id = self._score_duplicate_candidate(
                items,
                provider_counts,
                conflicts=conflicts,
            )
            confidence_factors = self._duplicate_confidence_factors(
                items,
                provider_counts,
                conflicts=conflicts,
            )
            merge_warnings = self._duplicate_merge_warnings(conflicts)
            candidates.append(
                AdminDuplicateCandidateResponse(
                    kind=kind.value if hasattr(kind, "value") else str(kind),
                    title=title,
                    item_number=item_number,
                    count=count,
                    item_ids=ids,
                    reason="same title and item number",
                    has_provider_conflicts=conflicts["provider"],
                    has_cover_conflicts=conflicts["cover"],
                    duplicate_score=duplicate_score,
                    recommended_target_item_id=recommended_target_item_id,
                    confidence_factors=confidence_factors,
                    merge_warnings=merge_warnings,
                )
            )
        candidates.sort(
            key=lambda candidate: (
                -candidate.duplicate_score,
                -candidate.count,
                candidate.title.lower(),
                (candidate.item_number or "").lower(),
            )
        )
        return candidates[:limit]

    async def ignore_duplicate_candidate(
        self,
        payload: AdminDuplicateIgnoreRequest,
    ) -> AdminDuplicateActionResponse:
        items = await self._items_by_ids(payload.item_ids)
        if len(items) != len(set(payload.item_ids)):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="duplicate_item_not_found",
                detail="One or more duplicate items were not found",
            )
        self._ensure_same_duplicate_group(items)
        token = self._duplicate_ignore_token([item.id for item in items])
        for item in items:
            metadata = dict(item.metadata_json or {})
            metadata["admin_duplicate_ignore_token"] = token
            metadata["admin_duplicate_ignored_at"] = datetime.now(UTC).isoformat()
            item.metadata_json = metadata
        self._audit_recorder(
            action="duplicates.ignore",
            entity_type="duplicate_group",
            details={
                "item_ids": [item.id for item in items],
                "kind": items[0].kind if items else None,
                "title": items[0].title if items else None,
                "item_number": items[0].item_number if items else None,
            },
        )
        await self.db.commit()
        return AdminDuplicateActionResponse(ok=True, affected_items=len(items))

    async def merge_duplicate_candidate(
        self,
        payload: AdminDuplicateMergeRequest,
    ) -> AdminDuplicateActionResponse:
        source_ids = [
            item_id for item_id in payload.source_item_ids if item_id != payload.target_item_id
        ]
        if not source_ids:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_source_required",
                detail="At least one source item different from target_item_id is required",
            )
        items = await self._items_by_ids([payload.target_item_id, *source_ids])
        if len(items) != len({payload.target_item_id, *source_ids}):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="duplicate_item_not_found",
                detail="One or more duplicate items were not found",
            )
        target = next(item for item in items if item.id == payload.target_item_id)
        sources = [item for item in items if item.id != payload.target_item_id]
        self._ensure_same_duplicate_group([target, *sources])

        for source in sources:
            await self._move_item_children(source, target)
            await self.db.delete(source)
        self._audit_recorder(
            action="duplicates.merge",
            entity_type="item",
            entity_id=target.id,
            details={
                "target_item_id": target.id,
                "source_item_ids": [source.id for source in sources],
                "kind": target.kind,
                "title": target.title,
                "item_number": target.item_number,
            },
        )
        await self.db.commit()

        loaded_item = await MetadataRepository(self.db).get_item(target.id)
        if loaded_item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="merged_target_unavailable",
                detail="Merged target item could not be loaded",
            )
        response_item = await self._item_response_loader(loaded_item)
        return AdminDuplicateActionResponse(
            ok=True,
            affected_items=len(sources),
            item=response_item,
        )

    async def duplicate_group_count(self) -> int:
        return len(await self.duplicate_candidates(limit=200))

    async def _items_by_ids(self, item_ids: list[UUID]) -> list[Item]:
        unique_ids = list(dict.fromkeys(item_ids))
        result = await self.db.execute(
            select(Item)
            .options(
                selectinload(Item.volume).selectinload(Volume.series),
                selectinload(Item.editions).selectinload(Edition.variants),
                selectinload(Item.kind_metadata),
            )
            .where(Item.id.in_(unique_ids))
        )
        items_by_id = {item.id: item for item in result.scalars().unique()}
        return [items_by_id[item_id] for item_id in unique_ids if item_id in items_by_id]

    def _ensure_same_duplicate_group(self, items: list[Item]) -> None:
        if len(items) < 2:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_action_requires_multiple_items",
                detail="Duplicate action requires at least two items",
            )
        first = items[0]
        signature = (first.kind, first.title, first.item_number)
        if any((item.kind, item.title, item.item_number) != signature for item in items[1:]):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="duplicate_group_mismatch",
                detail="Duplicate action items must belong to the same candidate group",
            )

    async def _duplicate_group_is_ignored(self, item_ids: list[UUID]) -> bool:
        if len(item_ids) < 2:
            return False
        token = self._duplicate_ignore_token(item_ids)
        result = await self.db.execute(select(Item.metadata_json).where(Item.id.in_(item_ids)))
        metadata_rows = list(result.scalars())
        if len(metadata_rows) != len(item_ids):
            return False
        return all(
            isinstance(metadata, dict) and metadata.get("admin_duplicate_ignore_token") == token
            for metadata in metadata_rows
        )

    async def _duplicate_conflict_flags(self, item_ids: list[UUID]) -> dict[str, bool]:
        provider_result = await self.db.execute(
            select(ItemProviderLink.provider, ItemProviderLink.provider_item_id)
            .where(
                ItemProviderLink.item_id.in_(item_ids),
            )
            .order_by(ItemProviderLink.provider, ItemProviderLink.provider_item_id)
        )
        provider_ids_by_provider: dict[str, set[str]] = {}
        for provider, provider_item_id in provider_result.all():
            provider_ids_by_provider.setdefault(str(provider), set()).add(provider_item_id)
        has_provider_conflicts = any(len(ids) > 1 for ids in provider_ids_by_provider.values())

        cover_result = await self.db.execute(
            select(
                Variant.cover_image_url,
                Variant.thumbnail_image_url,
                Variant.cover_image_key,
                Variant.thumbnail_image_key,
            )
            .join(Edition, Variant.edition_id == Edition.id)
            .where(Edition.item_id.in_(item_ids))
        )
        cover_signatures = {
            tuple(value for value in row if value) for row in cover_result.all() if any(row)
        }
        return {
            "provider": has_provider_conflicts,
            "cover": len(cover_signatures) > 1,
        }

    def _score_duplicate_candidate(
        self,
        items: list[Item],
        provider_counts: dict[UUID, int],
        *,
        conflicts: dict[str, bool],
    ) -> tuple[int, UUID | None]:
        if len(items) < 2:
            return 0, None

        score = 55
        if not conflicts["provider"]:
            score += 12
        if not conflicts["cover"]:
            score += 8
        if provider_counts:
            score += 6
        if len(provider_counts) == len(items):
            score += 4
        if self._duplicate_items_share_publisher(items):
            score += 6
        if self._duplicate_items_share_release_marker(items):
            score += 5

        recommended_target_item_id = max(
            items,
            key=lambda item: self._duplicate_merge_target_score(
                item,
                provider_counts.get(item.id, 0),
            ),
        ).id
        return min(score, 99), recommended_target_item_id

    def _duplicate_confidence_factors(
        self,
        items: list[Item],
        provider_counts: dict[UUID, int],
        *,
        conflicts: dict[str, bool],
    ) -> list[str]:
        if len(items) < 2:
            return []
        factors: list[str] = []
        if not conflicts["provider"]:
            factors.append("provider_ids_consistent")
        if not conflicts["cover"]:
            factors.append("cover_images_consistent")
        if provider_counts:
            factors.append("provider_links_present")
        if len(provider_counts) == len(items):
            factors.append("provider_links_present_for_all_items")
        if self._duplicate_items_share_publisher(items):
            factors.append("publisher_aligned")
        if self._duplicate_items_share_release_marker(items):
            factors.append("release_markers_aligned")
        return factors

    def _duplicate_merge_warnings(self, conflicts: dict[str, bool]) -> list[str]:
        warnings: list[str] = []
        if conflicts["provider"]:
            warnings.append("provider_id_conflict")
        if conflicts["cover"]:
            warnings.append("cover_asset_conflict")
        return warnings

    async def _provider_link_counts_by_item(self, item_ids: list[UUID]) -> dict[UUID, int]:
        result = await self.db.execute(
            select(ItemProviderLink.item_id, func.count(ItemProviderLink.id))
            .where(
                ItemProviderLink.item_id.in_(item_ids),
            )
            .group_by(ItemProviderLink.item_id)
        )
        return {entity_id: count for entity_id, count in result.all()}

    def _duplicate_merge_target_score(
        self,
        item: Item,
        provider_link_count: int,
    ) -> tuple[int, int, int]:
        edition_count = len(item.editions)
        variant_count = sum(len(edition.variants) for edition in item.editions)
        score = provider_link_count * 25
        if self._item_has_cover(item):
            score += 14
        if self._item_has_release_marker(item):
            score += 8
        if self._item_has_publisher(item):
            score += 6
        score += edition_count * 3
        score += min(variant_count, 4)
        return score, provider_link_count, edition_count

    def _duplicate_items_share_publisher(self, items: list[Item]) -> bool:
        publishers = [self._item_primary_publisher(item) for item in items]
        return all(publisher is not None for publisher in publishers) and len(set(publishers)) == 1

    def _duplicate_items_share_release_marker(self, items: list[Item]) -> bool:
        markers = [self._item_release_marker(item) for item in items]
        return all(marker is not None for marker in markers) and len(set(markers)) == 1

    def _item_has_cover(self, item: Item) -> bool:
        for edition in item.editions:
            for variant in edition.variants:
                if any(
                    (
                        variant.cover_image_url,
                        variant.thumbnail_image_url,
                        variant.cover_image_key,
                        variant.thumbnail_image_key,
                    )
                ):
                    return True
        return False

    def _item_has_release_marker(self, item: Item) -> bool:
        return self._item_release_marker(item) is not None

    def _item_has_publisher(self, item: Item) -> bool:
        return self._item_primary_publisher(item) is not None

    def _item_primary_publisher(self, item: Item) -> str | None:
        for edition in item.editions:
            if edition.publisher and edition.publisher.strip():
                return edition.publisher.strip().lower()
        return None

    def _item_release_marker(self, item: Item) -> str | None:
        for edition in item.editions:
            if edition.release_date is not None:
                return edition.release_date.isoformat()
        return None

    def _duplicate_ignore_token(self, item_ids: list[UUID]) -> str:
        return "|".join(sorted(str(item_id) for item_id in item_ids))

    async def _move_item_children(self, source_item: Item, target_item: Item) -> None:
        editions = await self.db.scalars(select(Edition).where(Edition.item_id == source_item.id))
        for edition in editions:
            edition.item = target_item

        source_metadata = source_item.kind_metadata
        target_metadata = target_item.kind_metadata
        if source_metadata is not None:
            if target_metadata is None:
                source_metadata.item = target_item
                source_metadata.item_id = target_item.id
            else:
                merged_payload = item_kind_metadata_payload(target_metadata)
                for key, value in item_kind_metadata_payload(source_metadata).items():
                    current = merged_payload.get(key)
                    if current is None or current == [] or current == {}:
                        merged_payload[key] = value
                upsert_item_kind_metadata(target_item, merged_payload)

        provider_links = await self.db.scalars(
            select(ItemProviderLink).where(ItemProviderLink.item_id == source_item.id)
        )
        for link in provider_links:
            exists = await self.db.scalar(
                select(ItemProviderLink.id).where(
                    ItemProviderLink.item_id == target_item.id,
                    ItemProviderLink.provider == link.provider,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.item_id = target_item.id

        await self._move_organization_links(source_item.id, target_item.id)
        await self._move_person_links(source_item.id, target_item.id)
        await self._move_story_arc_links(source_item.id, target_item.id)
        await self._move_character_appearance_links(source_item.id, target_item.id)
        await self._move_tag_links(source_item.id, target_item.id)

        await self.db.execute(
            update(ImageAsset)
            .where(
                ImageAsset.entity_type == "item",
                ImageAsset.entity_id == source_item.id,
            )
            .values(entity_id=target_item.id)
        )

    async def _move_organization_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(EntityOrganization).where(
                EntityOrganization.entity_type == "item",
                EntityOrganization.entity_id == source_item_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityOrganization.id).where(
                    EntityOrganization.entity_type == "item",
                    EntityOrganization.entity_id == target_item_id,
                    EntityOrganization.organization_id == link.organization_id,
                    EntityOrganization.role == link.role,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_item_id

    async def _move_person_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(EntityPerson).where(
                EntityPerson.entity_type == "item",
                EntityPerson.entity_id == source_item_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityPerson.id).where(
                    EntityPerson.entity_type == "item",
                    EntityPerson.entity_id == target_item_id,
                    EntityPerson.person_id == link.person_id,
                    EntityPerson.role == link.role,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_item_id

    async def _move_story_arc_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(select(StoryArcItem).where(StoryArcItem.item_id == source_item_id))
        for link in links:
            exists = await self.db.scalar(
                select(StoryArcItem.id).where(
                    StoryArcItem.story_arc_id == link.story_arc_id,
                    StoryArcItem.item_id == target_item_id,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.item_id = target_item_id

    async def _move_character_appearance_links(
        self,
        source_item_id: UUID,
        target_item_id: UUID,
    ) -> None:
        links = await self.db.scalars(
            select(CharacterAppearance).where(CharacterAppearance.item_id == source_item_id)
        )
        for link in links:
            existing = await self.db.scalar(
                select(CharacterAppearance).where(
                    CharacterAppearance.character_id == link.character_id,
                    CharacterAppearance.item_id == target_item_id,
                )
            )
            if existing:
                if self._character_role_rank(link.role) > self._character_role_rank(existing.role):
                    existing.role = link.role
                await self.db.delete(link)
            else:
                link.item_id = target_item_id

    async def _move_tag_links(self, source_item_id: UUID, target_item_id: UUID) -> None:
        links = await self.db.scalars(
            select(EntityTag).where(
                EntityTag.entity_type == "item",
                EntityTag.entity_id == source_item_id,
            )
        )
        for link in links:
            exists = await self.db.scalar(
                select(EntityTag.id).where(
                    EntityTag.entity_type == "item",
                    EntityTag.entity_id == target_item_id,
                    EntityTag.tag_id == link.tag_id,
                )
            )
            if exists:
                await self.db.delete(link)
            else:
                link.entity_id = target_item_id