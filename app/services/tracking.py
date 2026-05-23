from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.canonical import Edition, Item, TrackingEntry, Variant
from app.models.user import User
from app.schemas.tracking import (
    AdminTrackingStatsResponse,
    TrackingCountResponse,
    TrackingDashboardResponse,
    TrackingEntryResponse,
    TrackingEntryUpsertRequest,
    TrackingFacetsResponse,
    TrackingItemStatsResponse,
    TrackingKindCountResponse,
    TrackingPeriodCountResponse,
    TrackingTopItemResponse,
)


class TrackingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_entries(
        self,
        user: User,
        *,
        kind: ItemKind | None = None,
        status_filter: str | None = None,
        source_type: str | None = None,
        item_id: UUID | None = None,
        limit: int = 50,
    ) -> list[TrackingEntryResponse]:
        stmt = self._entries_query(user.id, kind=kind, status_filter=status_filter, source_type=source_type, item_id=item_id)
        rows = (await self.db.execute(stmt.order_by(TrackingEntry.updated_at.desc()).limit(limit))).all()
        return [self._entry_response(entry, item) for entry, item in rows]

    async def get_entry(self, user: User, entry_id: UUID) -> TrackingEntryResponse:
        entry, item = await self._get_entry_with_item(user.id, entry_id)
        return self._entry_response(entry, item)

    async def upsert_entry(
        self,
        user: User,
        payload: TrackingEntryUpsertRequest,
    ) -> TrackingEntryResponse:
        item = await self.db.get(Item, payload.item_id)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="tracking_item_not_found",
                detail="Tracked item not found",
            )
        await self._validate_release_refs(payload)

        stmt = select(TrackingEntry).where(
            TrackingEntry.user_id == user.id,
            TrackingEntry.item_id == payload.item_id,
            TrackingEntry.deleted_at.is_(None),
        )
        if payload.source_type is None:
            stmt = stmt.where(TrackingEntry.source_type.is_(None))
        else:
            stmt = stmt.where(TrackingEntry.source_type == payload.source_type)

        entry = (await self.db.execute(stmt.order_by(TrackingEntry.updated_at.desc()))).scalars().first()
        if entry is None:
            entry = TrackingEntry(user_id=user.id, item_id=payload.item_id)
            self.db.add(entry)

        entry.edition_id = payload.edition_id
        entry.variant_id = payload.variant_id
        entry.source_type = payload.source_type
        entry.status = payload.status
        entry.rating = payload.rating
        entry.started_at = self._to_utc(payload.started_at)
        entry.finished_at = self._to_utc(payload.finished_at)
        entry.progress_current = payload.progress_current
        entry.progress_total = payload.progress_total
        entry.times_completed = payload.times_completed
        entry.notes = payload.notes
        entry.season_number = payload.season_number
        entry.episode_number = payload.episode_number
        entry.deleted_at = None

        await self.db.commit()
        await self.db.refresh(entry)
        return await self.get_entry(user, entry.id)

    async def delete_entry(self, user: User, entry_id: UUID) -> None:
        entry, _ = await self._get_entry_with_item(user.id, entry_id)
        entry.deleted_at = datetime.now(UTC)
        await self.db.commit()

    async def item_stats(self, user: User, item_id: UUID) -> TrackingItemStatsResponse:
        item = await self.db.get(Item, item_id)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="tracking_item_not_found",
                detail="Tracked item not found",
            )

        base = select(TrackingEntry).where(
            TrackingEntry.item_id == item_id,
            TrackingEntry.deleted_at.is_(None),
        )
        total_entries, unique_users = await self._aggregate_counts(base, distinct_users=True)
        average_rating, rating_count = await self._aggregate_rating(base)
        current_user_entry = await self._latest_user_item_entry(user.id, item_id)

        return TrackingItemStatsResponse(
            item_id=item.id,
            item_title=item.title,
            kind=item.kind,
            total_entries=total_entries,
            unique_users=unique_users,
            average_rating=average_rating,
            rating_count=rating_count,
            counts_by_status=await self._count_by_status(base),
            counts_by_source_type=await self._count_by_source_type(base),
            current_user_entry=None if current_user_entry is None else self._entry_response(current_user_entry, item),
        )

    async def dashboard(
        self,
        user: User,
        *,
        kind: ItemKind | None = None,
        status_filter: str | None = None,
        source_type: str | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
    ) -> TrackingDashboardResponse:
        base = self._entries_query(
            user.id,
            kind=kind,
            status_filter=status_filter,
            source_type=source_type,
            updated_from=updated_from,
            updated_to=updated_to,
        )
        entries_only = self._entries_only_query(
            user_id=user.id,
            kind=kind,
            status_filter=status_filter,
            source_type=source_type,
            updated_from=updated_from,
            updated_to=updated_to,
        )
        total_entries, _ = await self._aggregate_counts(entries_only)
        average_rating, rating_count = await self._aggregate_rating(entries_only)
        recent_rows = (
            await self.db.execute(base.order_by(TrackingEntry.updated_at.desc()).limit(5))
        ).all()
        return TrackingDashboardResponse(
            total_entries=total_entries,
            average_rating=average_rating,
            rating_count=rating_count,
            counts_by_status=await self._count_by_status(entries_only),
            counts_by_kind=await self._count_by_kind(
                user_id=user.id,
                kind=kind,
                status_filter=status_filter,
                source_type=source_type,
                updated_from=updated_from,
                updated_to=updated_to,
            ),
            counts_by_source_type=await self._count_by_source_type(entries_only),
            recent_entries=[self._entry_response(entry, item) for entry, item in recent_rows],
        )

    async def dashboard_facets(
        self,
        user: User,
        *,
        kind: ItemKind | None = None,
        status_filter: str | None = None,
        source_type: str | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
    ) -> TrackingFacetsResponse:
        entries_only = self._entries_only_query(
            user_id=user.id,
            kind=kind,
            status_filter=status_filter,
            source_type=source_type,
            updated_from=updated_from,
            updated_to=updated_to,
        )
        return TrackingFacetsResponse(
            counts_by_status=await self._count_by_status(entries_only),
            counts_by_kind=await self._count_by_kind(
                user_id=user.id,
                kind=kind,
                status_filter=status_filter,
                source_type=source_type,
                updated_from=updated_from,
                updated_to=updated_to,
            ),
            counts_by_source_type=await self._count_by_source_type(entries_only),
            counts_by_period=await self._count_by_period(entries_only),
        )

    async def admin_stats(
        self,
        *,
        kind: ItemKind | None = None,
        status_filter: str | None = None,
        source_type: str | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
        limit: int = 10,
    ) -> AdminTrackingStatsResponse:
        base_entries = self._entries_only_query(
            kind=kind,
            status_filter=status_filter,
            source_type=source_type,
            updated_from=updated_from,
            updated_to=updated_to,
        )
        total_entries, unique_users = await self._aggregate_counts(base_entries, distinct_users=True)
        average_rating, rating_count = await self._aggregate_rating(base_entries)
        subquery = base_entries.subquery()
        unique_items = await self.db.scalar(
            select(func.count(distinct(subquery.c.item_id))).select_from(subquery)
        )
        return AdminTrackingStatsResponse(
            total_entries=total_entries,
            unique_users=unique_users,
            unique_items=int(unique_items or 0),
            average_rating=average_rating,
            rating_count=rating_count,
            counts_by_status=await self._count_by_status(base_entries),
            counts_by_kind=await self._count_by_kind(
                kind=kind,
                status_filter=status_filter,
                source_type=source_type,
                updated_from=updated_from,
                updated_to=updated_to,
            ),
            counts_by_source_type=await self._count_by_source_type(base_entries),
            top_items=await self._top_items(
                kind=kind,
                status_filter=status_filter,
                source_type=source_type,
                updated_from=updated_from,
                updated_to=updated_to,
                limit=limit,
            ),
        )

    async def admin_facets(
        self,
        *,
        kind: ItemKind | None = None,
        status_filter: str | None = None,
        source_type: str | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
    ) -> TrackingFacetsResponse:
        entries_only = self._entries_only_query(
            kind=kind,
            status_filter=status_filter,
            source_type=source_type,
            updated_from=updated_from,
            updated_to=updated_to,
        )
        return TrackingFacetsResponse(
            counts_by_status=await self._count_by_status(entries_only),
            counts_by_kind=await self._count_by_kind(
                kind=kind,
                status_filter=status_filter,
                source_type=source_type,
                updated_from=updated_from,
                updated_to=updated_to,
            ),
            counts_by_source_type=await self._count_by_source_type(entries_only),
            counts_by_period=await self._count_by_period(entries_only),
        )

    def _entries_query(
        self,
        user_id: UUID,
        *,
        kind: ItemKind | None = None,
        status_filter: str | None = None,
        source_type: str | None = None,
        item_id: UUID | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
    ):
        stmt = select(TrackingEntry, Item).join(Item, Item.id == TrackingEntry.item_id).where(
            TrackingEntry.user_id == user_id,
            TrackingEntry.deleted_at.is_(None),
        )
        if kind is not None:
            stmt = stmt.where(Item.kind == kind)
        if status_filter is not None:
            stmt = stmt.where(TrackingEntry.status == status_filter)
        if source_type is not None:
            stmt = stmt.where(TrackingEntry.source_type == source_type)
        if item_id is not None:
            stmt = stmt.where(TrackingEntry.item_id == item_id)
        if updated_from is not None:
            stmt = stmt.where(TrackingEntry.updated_at >= self._to_utc(updated_from))
        if updated_to is not None:
            stmt = stmt.where(TrackingEntry.updated_at <= self._to_utc(updated_to))
        return stmt

    def _entries_only_query(
        self,
        *,
        user_id: UUID | None = None,
        kind: ItemKind | None = None,
        status_filter: str | None = None,
        source_type: str | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
    ):
        stmt = select(TrackingEntry).join(Item, Item.id == TrackingEntry.item_id).where(
            TrackingEntry.deleted_at.is_(None)
        )
        if user_id is not None:
            stmt = stmt.where(TrackingEntry.user_id == user_id)
        if kind is not None:
            stmt = stmt.where(Item.kind == kind)
        if status_filter is not None:
            stmt = stmt.where(TrackingEntry.status == status_filter)
        if source_type is not None:
            stmt = stmt.where(TrackingEntry.source_type == source_type)
        if updated_from is not None:
            stmt = stmt.where(TrackingEntry.updated_at >= self._to_utc(updated_from))
        if updated_to is not None:
            stmt = stmt.where(TrackingEntry.updated_at <= self._to_utc(updated_to))
        return stmt

    async def _get_entry_with_item(self, user_id: UUID, entry_id: UUID) -> tuple[TrackingEntry, Item]:
        row = (
            await self.db.execute(
                select(TrackingEntry, Item)
                .join(Item, Item.id == TrackingEntry.item_id)
                .where(
                    TrackingEntry.id == entry_id,
                    TrackingEntry.user_id == user_id,
                    TrackingEntry.deleted_at.is_(None),
                )
            )
        ).first()
        if row is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="tracking_entry_not_found",
                detail="Tracking entry not found",
            )
        return row

    async def _validate_release_refs(self, payload: TrackingEntryUpsertRequest) -> None:
        if payload.edition_id is not None:
            edition = await self.db.get(Edition, payload.edition_id)
            if edition is None or edition.item_id != payload.item_id:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="tracking_invalid_edition",
                    detail="Edition does not belong to tracked item",
                )
        if payload.variant_id is not None:
            variant = await self.db.get(Variant, payload.variant_id)
            if variant is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="tracking_invalid_variant",
                    detail="Variant not found",
                )
            if payload.edition_id is not None and variant.edition_id != payload.edition_id:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="tracking_variant_edition_mismatch",
                    detail="Variant does not belong to selected edition",
                )

    async def _aggregate_counts(self, stmt, *, distinct_users: bool = False) -> tuple[int, int]:
        subquery = stmt.subquery()
        total_entries = await self.db.scalar(select(func.count()).select_from(subquery))
        unique_users = 0
        if distinct_users:
            unique_users = int(
                (
                    await self.db.scalar(
                        select(func.count(distinct(subquery.c.user_id))).select_from(subquery)
                    )
                )
                or 0
            )
        return int(total_entries or 0), unique_users

    async def _aggregate_rating(self, stmt) -> tuple[float | None, int]:
        subquery = stmt.subquery()
        row = (
            await self.db.execute(
                select(func.avg(subquery.c.rating), func.count(subquery.c.rating)).select_from(subquery)
            )
        ).one()
        average_rating = None if row[0] is None else float(row[0])
        return average_rating, int(row[1] or 0)

    async def _count_by_status(self, stmt) -> list[TrackingCountResponse]:
        subquery = stmt.subquery()
        rows = (
            await self.db.execute(
                select(subquery.c.status, func.count())
                .where(subquery.c.status.is_not(None))
                .group_by(subquery.c.status)
                .order_by(func.count().desc(), subquery.c.status.asc())
            )
        ).all()
        return [TrackingCountResponse(key=str(key), count=int(count)) for key, count in rows]

    async def _count_by_source_type(self, stmt) -> list[TrackingCountResponse]:
        subquery = stmt.subquery()
        rows = (
            await self.db.execute(
                select(subquery.c.source_type, func.count())
                .where(subquery.c.source_type.is_not(None))
                .group_by(subquery.c.source_type)
                .order_by(func.count().desc(), subquery.c.source_type.asc())
            )
        ).all()
        return [TrackingCountResponse(key=str(key), count=int(count)) for key, count in rows]

    async def _count_by_kind(
        self,
        *,
        user_id: UUID | None = None,
        kind: ItemKind | None = None,
        status_filter: str | None = None,
        source_type: str | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
    ) -> list[TrackingKindCountResponse]:
        stmt = select(Item.kind, func.count()).join(TrackingEntry, TrackingEntry.item_id == Item.id).where(
            TrackingEntry.deleted_at.is_(None)
        )
        if user_id is not None:
            stmt = stmt.where(TrackingEntry.user_id == user_id)
        if kind is not None:
            stmt = stmt.where(Item.kind == kind)
        if status_filter is not None:
            stmt = stmt.where(TrackingEntry.status == status_filter)
        if source_type is not None:
            stmt = stmt.where(TrackingEntry.source_type == source_type)
        if updated_from is not None:
            stmt = stmt.where(TrackingEntry.updated_at >= self._to_utc(updated_from))
        if updated_to is not None:
            stmt = stmt.where(TrackingEntry.updated_at <= self._to_utc(updated_to))
        rows = (await self.db.execute(stmt.group_by(Item.kind).order_by(func.count().desc(), Item.kind.asc()))).all()
        return [TrackingKindCountResponse(kind=item_kind, count=int(count)) for item_kind, count in rows]

    async def _count_by_period(self, stmt) -> list[TrackingPeriodCountResponse]:
        subquery = stmt.subquery()
        period_key = func.to_char(func.date_trunc("month", subquery.c.updated_at), "YYYY-MM")
        rows = (
            await self.db.execute(
                select(period_key, func.count())
                .group_by(period_key)
                .order_by(period_key.asc())
            )
        ).all()
        return [TrackingPeriodCountResponse(period=str(period), count=int(count)) for period, count in rows]

    async def _top_items(
        self,
        *,
        kind: ItemKind | None = None,
        status_filter: str | None = None,
        source_type: str | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
        limit: int = 10,
    ) -> list[TrackingTopItemResponse]:
        stmt = select(Item.id, Item.title, Item.kind, func.count()).join(
            TrackingEntry, TrackingEntry.item_id == Item.id
        ).where(TrackingEntry.deleted_at.is_(None))
        if kind is not None:
            stmt = stmt.where(Item.kind == kind)
        if status_filter is not None:
            stmt = stmt.where(TrackingEntry.status == status_filter)
        if source_type is not None:
            stmt = stmt.where(TrackingEntry.source_type == source_type)
        if updated_from is not None:
            stmt = stmt.where(TrackingEntry.updated_at >= self._to_utc(updated_from))
        if updated_to is not None:
            stmt = stmt.where(TrackingEntry.updated_at <= self._to_utc(updated_to))
        rows = (
            await self.db.execute(
                stmt.group_by(Item.id, Item.title, Item.kind)
                .order_by(func.count().desc(), Item.title.asc())
                .limit(limit)
            )
        ).all()
        return [
            TrackingTopItemResponse(item_id=item_id, title=title, kind=item_kind, count=int(count))
            for item_id, title, item_kind, count in rows
        ]

    async def _latest_user_item_entry(self, user_id: UUID, item_id: UUID) -> TrackingEntry | None:
        return (
            await self.db.execute(
                select(TrackingEntry)
                .where(
                    TrackingEntry.user_id == user_id,
                    TrackingEntry.item_id == item_id,
                    TrackingEntry.deleted_at.is_(None),
                )
                .order_by(TrackingEntry.updated_at.desc())
            )
        ).scalars().first()

    def _entry_response(self, entry: TrackingEntry, item: Item) -> TrackingEntryResponse:
        return TrackingEntryResponse(
            id=entry.id,
            user_id=entry.user_id,
            item_id=entry.item_id,
            item_title=item.title,
            kind=item.kind,
            edition_id=entry.edition_id,
            variant_id=entry.variant_id,
            source_type=entry.source_type,
            status=entry.status,
            rating=entry.rating,
            started_at=entry.started_at,
            finished_at=entry.finished_at,
            progress_current=entry.progress_current,
            progress_total=entry.progress_total,
            times_completed=entry.times_completed,
            notes=entry.notes,
            season_number=entry.season_number,
            episode_number=entry.episode_number,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            deleted_at=entry.deleted_at,
        )

    def _to_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)