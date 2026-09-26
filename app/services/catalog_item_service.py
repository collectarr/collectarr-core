from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiHTTPException
from app.models.canonical_catalog_items import CanonicalCatalogItem
from app.schemas.catalog_item_v1 import (
    CATALOG_ITEM_DETAILS_BY_KIND,
    CatalogItemSummaryV1,
    CatalogItemV1,
    CatalogItemWriteV1,
)


class CatalogItemService:
    """Source-neutral CRUD and search for concrete catalog items."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_item(self, item_id: UUID, *, kind: str | None = None) -> CatalogItemV1:
        stmt = select(CanonicalCatalogItem).where(CanonicalCatalogItem.id == item_id)
        if kind is not None:
            stmt = stmt.where(CanonicalCatalogItem.kind == kind)
        item = await self.db.scalar(stmt)
        if item is None:
            raise ApiHTTPException(
                status_code=404,
                code="catalog_item_not_found",
                detail=f"Catalog item {item_id} was not found.",
            )
        return self._response(item)

    async def search_items(
        self,
        *,
        kind: str | None = None,
        query: str | None = None,
        identifier: str | None = None,
        limit: int = 50,
    ) -> list[CatalogItemSummaryV1]:
        stmt = select(CanonicalCatalogItem).order_by(
            CanonicalCatalogItem.kind.asc(),
            CanonicalCatalogItem.sort_title.asc().nullslast(),
            CanonicalCatalogItem.title.asc(),
            CanonicalCatalogItem.id.asc(),
        )
        if kind is not None:
            stmt = stmt.where(CanonicalCatalogItem.kind == kind)
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    CanonicalCatalogItem.title.ilike(pattern),
                    CanonicalCatalogItem.sort_title.ilike(pattern),
                    cast(CanonicalCatalogItem.details, Text).ilike(pattern),
                )
            )
        if identifier and identifier.strip():
            normalized = _normalize_identifier(identifier)
            if not normalized:
                return []
            stmt = stmt.where(CanonicalCatalogItem.identifier_search.contains(f"|{normalized}|"))

        rows = list((await self.db.execute(stmt.limit(max(1, min(limit, 200))))).scalars())
        return [self._summary(row) for row in rows]

    async def create_item(self, payload: CatalogItemWriteV1) -> CatalogItemV1:
        details = payload.details
        values = details.model_dump(mode="json")
        item = CanonicalCatalogItem(
            id=uuid4(),
            kind=details.kind,
            title=details.title.strip(),
            sort_title=details.sort_title,
            identifier_search=_identifier_search_text(values),
            details=values,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.commit()
        loaded = await self.db.scalar(
            select(CanonicalCatalogItem).where(CanonicalCatalogItem.id == item.id)
        )
        assert loaded is not None
        return self._response(loaded)

    async def update_item(
        self,
        item_id: UUID,
        payload: CatalogItemWriteV1,
        *,
        kind: str | None = None,
    ) -> CatalogItemV1:
        item = await self.db.scalar(
            select(CanonicalCatalogItem).where(CanonicalCatalogItem.id == item_id)
        )
        if item is None or (kind is not None and item.kind != kind):
            raise ApiHTTPException(
                status_code=404,
                code="catalog_item_not_found",
                detail=f"Catalog item {item_id} was not found.",
            )
        details = payload.details
        if details.kind != item.kind:
            raise ApiHTTPException(
                status_code=422,
                code="catalog_item_kind_mismatch",
                detail=(
                    f"Catalog item {item_id} is kind '{item.kind}', but the request "
                    f"contains kind '{details.kind}'."
                ),
            )
        values = details.model_dump(mode="json")
        item.title = details.title.strip()
        item.sort_title = details.sort_title
        item.identifier_search = _identifier_search_text(values)
        item.details = values
        await self.db.flush()
        await self.db.commit()
        return self._response(item)

    @staticmethod
    def _response(item: CanonicalCatalogItem) -> CatalogItemV1:
        detail_type = CATALOG_ITEM_DETAILS_BY_KIND[item.kind]
        details = detail_type.model_validate(_response_details(item))
        return CatalogItemV1(
            id=item.id,
            details=details,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    @classmethod
    def _summary(cls, item: CanonicalCatalogItem) -> CatalogItemSummaryV1:
        details_type = CATALOG_ITEM_DETAILS_BY_KIND[item.kind]
        details = details_type.model_validate(_response_details(item))
        cover_url = _cover_image_url(item.details)
        return CatalogItemSummaryV1(
            id=item.id,
            kind=item.kind,
            title=item.title,
            sort_title=item.sort_title,
            release_date=getattr(details, "release_date", None),
            cover_image_url=cover_url,
        )


def _response_details(item: CanonicalCatalogItem) -> dict[str, Any]:
    details = dict(item.details)
    if item.kind == "music":
        tracks = details.get("tracks")
        if isinstance(tracks, list):
            details["tracks"] = [
                {**track, "album_id": str(item.id)} if isinstance(track, dict) else track
                for track in tracks
            ]
    return details


def _cover_image_url(details: dict[str, Any]) -> str | None:
    direct_url = details.get("cover_image_url")
    if isinstance(direct_url, str) and direct_url.strip():
        return direct_url
    images = details.get("images")
    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict):
                url = image.get("url")
                if isinstance(url, str) and url.strip():
                    return url
    return None


def _identifier_search_text(details: dict[str, Any]) -> str:
    values: list[str] = []

    def visit(value: Any, field_name: str = "") -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                visit(nested, key.lower())
        elif isinstance(value, list):
            for nested in value:
                visit(nested, field_name)
        elif field_name in {"value", "barcode", "catalog_number", "isbn"}:
            normalized = _normalize_identifier(str(value))
            if normalized:
                values.append(normalized)

    visit(details)
    unique_values = dict.fromkeys(values)
    return f"|{'|'.join(unique_values)}|" if unique_values else ""


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())
