"""Read and write operations for flattened Comic Catalog Items."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Integer, and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.catalog.kind_registry import catalog_kind_for
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.catalog_comic_item import ComicItem
from app.schemas.catalog_comic_item import CatalogComicItemResponse, CatalogComicSeriesResponse
from app.schemas.metadata_shared import CatalogSearchItemEnvelope
from app.services.catalog_item_search import CatalogItemSearchService


class CatalogComicItemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_from_proposal(
        self,
        submitted: dict[str, Any],
    ) -> CatalogComicItemResponse:
        payload = validate_catalog_item_payload(ItemKind.comic, submitted)
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Comic Catalog Item title must not be empty")

        raw_identifiers = payload.get("identifiers", []) or []
        identifiers = [
            identifier
            for identifier in (_identifier(value) for value in raw_identifiers)
            if identifier is not None
        ]
        identifier_keys = {
            (row["identifier_type"], row["normalized_value"]) for row in identifiers
        }
        if len(identifier_keys) != len(identifiers):
            raise ValueError("Comic identifiers must be unique by type and normalized value")

        item = ComicItem(
            title=title.strip(),
            sort_key=_optional_string(payload.pop("sort_key", None)),
            barcode=_optional_string(payload.pop("barcode", None)),
            catalog_number=_optional_string(payload.pop("catalog_number", None)),
            details={**payload, "identifiers": identifiers},
        )
        self.db.add(item)
        await self.db.flush()
        return _response(item)

    async def search(
        self,
        *,
        query: str | None,
        barcode: str | None,
        limit: int,
        offset: int,
    ) -> list[CatalogComicItemResponse]:
        statement = select(ComicItem)
        if barcode and barcode.strip():
            exact = barcode.strip()
            statement = statement.where(
                or_(
                    ComicItem.barcode == exact,
                    ComicItem.details.contains(
                        {"identifiers": [{"normalized_value": _normalize(exact)}]}
                    ),
                )
            )
        elif query and query.strip():
            exact = query.strip()
            term = f"%{exact}%"
            statement = statement.where(
                or_(
                    ComicItem.title.ilike(term),
                    ComicItem.sort_key.ilike(term),
                    ComicItem.barcode == exact,
                    ComicItem.catalog_number == exact,
                    ComicItem.details.contains(
                        {"identifiers": [{"normalized_value": _normalize(exact)}]}
                    ),
                )
            )
        statement = (
            statement.order_by(
                ComicItem.sort_key.asc().nullslast(),
                ComicItem.title.asc(),
                ComicItem.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(statement)
        return [_response(item) for item in result.scalars().unique()]

    async def search_series(self, *, query: str, limit: int) -> list[CatalogComicSeriesResponse]:
        """Series whose title contains [query]; an exact title sorts first."""
        series, publisher, volume = _series_columns()
        year = ComicItem.details["release_date_parts"]["year"].astext.cast(Integer)
        cover = ComicItem.details["cover_image_url"].astext
        exact = query.strip()
        rows = (
            await self.db.execute(
                select(
                    series,
                    publisher,
                    volume,
                    func.min(year),
                    func.max(year),
                    func.count(),
                    func.array_agg(aggregate_order_by(cover, *_issue_order())).filter(cover.isnot(None))[1],
                )
                .where(series.ilike(f"%{exact}%"))
                .group_by(series, publisher, volume)
                .order_by(
                    case((func.lower(series) == exact.lower(), 0), else_=1),
                    func.lower(series),
                    volume.asc().nullsfirst(),
                    func.lower(publisher).asc().nullsfirst(),
                )
                .limit(limit)
            )
        ).all()
        return [
            CatalogComicSeriesResponse(
                series_title=title,
                publisher=publisher_value,
                volume_start_year=volume_value,
                first_year=first_year,
                last_year=last_year,
                issue_count=count,
                cover_image_url=cover_value,
            )
            for title, publisher_value, volume_value, first_year, last_year, count, cover_value in rows
        ]

    async def series_issues(
        self,
        *,
        series_title: str,
        publisher: str | None,
        volume_start_year: int | None,
    ) -> list[CatalogSearchItemEnvelope]:
        """Every issue and variant of one series, in issue order."""
        series, publisher_column, volume = _series_columns()
        rows = (
            await self.db.execute(
                select(ComicItem)
                .where(
                    and_(
                        series == series_title,
                        publisher_column.is_(None) if publisher is None else publisher_column == publisher,
                        volume.is_(None) if volume_start_year is None else volume == volume_start_year,
                    )
                )
                .order_by(*_issue_order())
                .limit(_SERIES_ISSUE_LIMIT)
            )
        ).scalars().all()
        root = catalog_kind_for(ItemKind.comic)
        return [CatalogItemSearchService.to_search_envelope(root, item) for item in rows]

    async def get(self, item_id: UUID) -> CatalogComicItemResponse:
        result = await self.db.execute(
            select(ComicItem)
            .where(ComicItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise ApiHTTPException(
                status_code=404,
                code="comic_item_not_found",
                detail="Comic Catalog Item not found",
            )
        return _response(item)


# A series lists all its issues at once; this bounds a malformed catalog.
_SERIES_ISSUE_LIMIT = 2000


def _series_columns():
    details = ComicItem.details
    return (
        details["series_title"].astext,
        details["publisher"].astext,
        details["volume_start_year"].astext.cast(Integer),
    )


def _issue_order():
    """Numeric issue numbers in value order, then text numbers, then variants."""
    issue = ComicItem.details["issue_number"].astext
    numeric = func.substring(issue, r"^\d+").cast(Integer)
    return (
        numeric.asc().nullslast(),
        issue.asc().nullslast(),
        ComicItem.details["variant"].astext.asc().nullsfirst(),
        ComicItem.title.asc(),
        ComicItem.id.asc(),
    )


def _response(item: ComicItem) -> CatalogComicItemResponse:
    fields = dict(item.details)
    fields.update(
        {
            "title": item.title,
            "sort_key": item.sort_key,
            "barcode": item.barcode,
            "catalog_number": item.catalog_number,
        }
    )
    return CatalogComicItemResponse.model_validate(
        {"id": item.id, "kind": "comic", "revision": item.revision, **fields}
    )


def _identifier(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        identifier_type = "other"
        raw_value = value.strip()
        normalized_value = _normalize(raw_value)
        is_primary = False
    elif isinstance(value, Mapping):
        identifier_type = _optional_string(value.get("identifier_type")) or "other"
        raw_value = _optional_string(value.get("value"))
        normalized_value = _optional_string(value.get("normalized_value")) or _normalize(
            raw_value or ""
        )
        is_primary = value.get("is_primary") is True
    else:
        return None
    if not raw_value:
        return None
    try:
        identifier_id = str(UUID(str(value.get("id")))) if isinstance(value, Mapping) and value.get("id") else str(uuid4())
    except ValueError as error:
        raise ValueError("Comic identifier id must be a UUID") from error
    return {
        "id": identifier_id,
        "identifier_type": identifier_type,
        "value": raw_value,
        "normalized_value": normalized_value,
        "is_primary": is_primary,
    }


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None
