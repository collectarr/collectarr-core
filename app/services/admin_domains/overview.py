import logging
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AdminAuditLog,
    ImageAsset,
    ImageCacheEntry,
)
from app.models.base import ItemKind
from app.models.canonical_catalog_items import CanonicalCatalogItem
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminCatalogSummaryResponse,
    AdminSearchHistoryEntry,
    AdminSearchReindexResponse,
    AdminSearchStatusResponse,
)
from app.search.client import SearchClient
from app.services.typed_values import materialize_typed_values

_SEARCH_HISTORY: deque[AdminSearchHistoryEntry] = deque(maxlen=20)
logger = logging.getLogger(__name__)


def _meili_document_count(stats: Any) -> int | None:
    if isinstance(stats, dict):
        value = stats.get("numberOfDocuments")
        if value is None:
            value = stats.get("number_of_documents")
    else:
        value = getattr(stats, "number_of_documents", None)
        if value is None:
            value = getattr(stats, "numberOfDocuments", None)
        if value is None and hasattr(stats, "model_dump"):
            dumped = stats.model_dump(by_alias=True)
            value = dumped.get("numberOfDocuments")
            if value is None:
                value = dumped.get("number_of_documents")
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            return None
    return value if isinstance(value, int) else None


class AdminOverviewService:
    def __init__(
        self,
        *,
        db: AsyncSession,
        search_client_cls: type[SearchClient] | None = None,
        duplicate_group_count: Callable[[], Awaitable[int]],
    ) -> None:
        self.db = db
        self.search_client_cls = search_client_cls or SearchClient
        self._duplicate_group_count = duplicate_group_count

    async def catalog_summary(self) -> AdminCatalogSummaryResponse:
        duplicate_groups = await self._duplicate_group_count()
        items_by_kind = await self._item_counts_by_kind()
        return AdminCatalogSummaryResponse(
            items=sum(items_by_kind.values()),
            items_by_kind=items_by_kind,
            image_assets=await self._count_image_assets(),
            image_cache_entries=await self._count(ImageCacheEntry),
            missing_cover_items=await self._count_missing_cover_items(),
            duplicate_candidate_groups=duplicate_groups,
        )

    async def search_status(self) -> AdminSearchStatusResponse:
        try:
            client = self.search_client_cls()
            client.client.health()
            stats = client.client.index(client.index_name).get_stats()
            document_count = _meili_document_count(stats)
        except Exception as exc:
            logger.warning("admin_search_status_failed error=%s", exc)
            return AdminSearchStatusResponse(
                ok=False,
                index_name=self.search_client_cls.index_name,
                error=str(exc),
            )
        return AdminSearchStatusResponse(
            ok=True,
            index_name=client.index_name,
            document_count=document_count,
            is_empty=document_count == 0 if document_count is not None else None,
        )

    async def reindex_search(self) -> AdminSearchReindexResponse:
        search = self.search_client_cls()
        try:
            await search.configure()
            documents = await self._search_documents()
            await search.replace_documents(documents)
        except Exception as exc:
            logger.warning("admin_search_reindex_failed index=%s error=%s", search.index_name, exc)
            response = AdminSearchReindexResponse(
                ok=False,
                index_name=search.index_name,
                indexed_documents=0,
                error=str(exc),
            )
            self._record_search_history(response)
            return response
        response = AdminSearchReindexResponse(
            ok=True,
            index_name=search.index_name,
            indexed_documents=len(documents),
        )
        self._record_search_history(response)
        return response

    def search_history(self) -> list[AdminSearchHistoryEntry]:
        return list(_SEARCH_HISTORY)

    async def audit_logs(
        self,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        limit: int = 25,
    ) -> list[AdminAuditLogResponse]:
        stmt = select(AdminAuditLog).order_by(
            AdminAuditLog.created_at.desc(),
            AdminAuditLog.id.desc(),
        )
        if action:
            stmt = stmt.where(AdminAuditLog.action == action)
        if entity_type:
            stmt = stmt.where(AdminAuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AdminAuditLog.entity_id == entity_id)
        result = await self.db.execute(
            stmt.options(selectinload(AdminAuditLog.details)).limit(limit)
        )
        return [
            AdminAuditLogResponse.model_validate(row).model_copy(
                update={"details_json": materialize_typed_values(row.details)}
            )
            for row in result.scalars()
        ]

    async def _count(self, model: type) -> int:
        return int(await self.db.scalar(select(func.count()).select_from(model)) or 0)

    async def _item_counts_by_kind(self) -> dict[str, int]:
        counts = {kind.value: 0 for kind in ItemKind}
        result = await self.db.execute(
            select(CanonicalCatalogItem.kind, func.count()).group_by(CanonicalCatalogItem.kind)
        )
        for kind, count in result.all():
            if kind in counts:
                counts[kind] = int(count)
        return counts

    async def _count_image_assets(self) -> int:
        return await self._count(ImageAsset)

    async def _count_missing_cover_items(self) -> int:
        details_rows = await self.db.scalars(select(CanonicalCatalogItem.details))
        missing = 0
        for details in details_rows:
            direct_cover = details.get("cover_image_url")
            if isinstance(direct_cover, str) and direct_cover.strip():
                continue
            images = details.get("images")
            if isinstance(images, list) and any(
                isinstance(image, dict)
                and any(
                    isinstance(image.get(field), str) and image[field].strip()
                    for field in ("url", "image_key")
                )
                for image in images
            ):
                continue
            missing += 1
        return missing

    async def _search_documents(self) -> list[dict[str, Any]]:
        rows = await self.db.scalars(
            select(CanonicalCatalogItem).order_by(
                CanonicalCatalogItem.kind.asc(),
                CanonicalCatalogItem.sort_title.asc().nullslast(),
                CanonicalCatalogItem.title.asc(),
                CanonicalCatalogItem.id.asc(),
            )
        )
        return [_catalog_item_search_document(item) for item in rows]

    def _record_search_history(self, response: AdminSearchReindexResponse) -> None:
        _SEARCH_HISTORY.appendleft(
            AdminSearchHistoryEntry(
                timestamp=datetime.now(UTC),
                ok=response.ok,
                index_name=response.index_name,
                indexed_documents=response.indexed_documents,
                error=response.error,
            )
        )


def _catalog_item_search_document(item: CanonicalCatalogItem) -> dict[str, Any]:
    details = item.details if isinstance(item.details, dict) else {}
    identifiers = details.get("identifiers")
    identifiers = identifiers if isinstance(identifiers, list) else []
    barcodes = [
        value
        for entry in identifiers
        if isinstance(entry, dict)
        and str(entry.get("identifier_type", "")).casefold() in {"barcode", "ean", "gtin", "upc"}
        and (value := _nonempty(entry.get("value"))) is not None
    ]
    direct_barcode = _nonempty(details.get("barcode"))
    if direct_barcode and direct_barcode not in barcodes:
        barcodes.insert(0, direct_barcode)

    release_date = details.get("release_date") or details.get("publication_date")
    release_year = _partial_year(release_date)
    item_number = next(
        (
            value
            for key in ("issue_number", "volume_number", "season_number")
            if (value := _nonempty(details.get(key))) is not None
        ),
        None,
    )
    publisher = _nonempty(details.get("publisher")) or _first_string(
        details.get("publishers")
    ) or _first_dict_string(details.get("labels"), "name")
    creators = _strings(details.get("artists")) + _credit_names(
        details.get("credits") or details.get("contributors") or details.get("creators")
    )
    catalog_number = _nonempty(details.get("catalog_number")) or _first_dict_string(
        details.get("labels"), "catalog_number"
    )

    return {
        "id": str(item.id),
        "kind": item.kind,
        "title": item.title,
        "sort_title": item.sort_title,
        "item_number": item_number,
        "publisher": publisher,
        "release_date": _partial_date_string(release_date),
        "release_year": release_year,
        "barcode": direct_barcode or (barcodes[0] if barcodes else None),
        "barcodes": barcodes,
        "catalog_number": catalog_number,
        "cover_image_url": _cover_image_url(details),
        "thumbnail_image_url": _first_dict_string(details.get("images"), "thumbnail_url"),
        "region": _nonempty(details.get("region")) or _nonempty(details.get("country")),
        "platforms": _strings(details.get("platforms")),
        "creators": list(dict.fromkeys(creators)),
        "characters": _strings(details.get("characters")),
        "story_arcs": _strings(details.get("story_arcs")),
        "language": _nonempty(details.get("language")),
        "imprint": _nonempty(details.get("imprint")),
        "subtitle": _nonempty(details.get("subtitle")),
        "series_group": _nonempty(details.get("series_title")),
        "age_rating": _nonempty(details.get("age_rating")),
        "release_status": _nonempty(details.get("release_status")),
        "bundle_titles": _contained_titles(details),
        "runtime_minutes": details.get("runtime_minutes"),
    }


def _nonempty(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int):
        return str(value)
    return None


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for entry in value if (text := _nonempty(entry)) is not None]


def _first_string(value: Any) -> str | None:
    values = _strings(value)
    return values[0] if values else None


def _credit_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        text
        for entry in value
        if isinstance(entry, dict)
        and (text := _nonempty(entry.get("name") or entry.get("credited_name"))) is not None
    ]


def _first_dict_string(value: Any, key: str) -> str | None:
    if not isinstance(value, list):
        return None
    for entry in value:
        if isinstance(entry, dict) and (text := _nonempty(entry.get(key))) is not None:
            return text
    return None


def _partial_date_string(value: Any) -> str | None:
    if isinstance(value, dict):
        year, month, day = (value.get(key) for key in ("year", "month", "day"))
        if not isinstance(year, int):
            return None
        result = f"{year:04d}"
        if isinstance(month, int):
            result += f"-{month:02d}"
            if isinstance(day, int):
                result += f"-{day:02d}"
        return result
    if isinstance(value, str):
        return value
    return None


def _partial_year(value: Any) -> int | None:
    if isinstance(value, dict):
        year = value.get("year")
        return year if isinstance(year, int) else None
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return None


def _cover_image_url(details: dict[str, Any]) -> str | None:
    direct = _nonempty(details.get("cover_image_url"))
    if direct:
        return direct
    return _first_dict_string(details.get("images"), "url")


def _contained_titles(details: dict[str, Any]) -> list[str]:
    titles: list[str] = []
    for key in ("tracks", "episodes", "seasons", "media_tracks", "components"):
        entries = details.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            title = _nonempty(entry.get("title") or entry.get("name"))
            if title:
                titles.append(title)
    return titles
