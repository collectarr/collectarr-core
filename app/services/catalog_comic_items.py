"""Read and write operations for flattened Comic Catalog Items."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.catalog_comic_item import ComicItem
from app.schemas.catalog_comic_item import CatalogComicItemResponse


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
