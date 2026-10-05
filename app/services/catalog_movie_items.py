"""Read and write operations for flattened Movie Catalog Items."""

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
from app.models.catalog_movie_item import MovieItem
from app.schemas.catalog_movie_item import CatalogMovieItemResponse


class CatalogMovieItemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_from_proposal(
        self,
        submitted: dict[str, Any],
    ) -> CatalogMovieItemResponse:
        item_payload = validate_catalog_item_payload(ItemKind.movie, submitted)
        title = item_payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Movie Catalog Item title must not be empty")

        media_payload = item_payload.get("media", []) or []
        item_payload["media"] = _contained_media(media_payload)
        item_payload["identifiers"] = _normalize_identifiers(item_payload.get("identifiers", []))
        item = MovieItem(
            title=title.strip(),
            sort_key=_optional_string(item_payload.get("sort_key")),
            barcode=_optional_string(item_payload.get("barcode")),
            catalog_number=_optional_string(item_payload.get("catalog_number")),
            details=item_payload,
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
    ) -> list[CatalogMovieItemResponse]:
        statement = select(MovieItem)
        if barcode and barcode.strip():
            statement = statement.where(MovieItem.barcode == barcode.strip())
        elif query and query.strip():
            term = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    MovieItem.title.ilike(term),
                    MovieItem.sort_key.ilike(term),
                    MovieItem.barcode == query.strip(),
                    MovieItem.catalog_number == query.strip(),
                )
            )
        statement = (
            statement.order_by(
                MovieItem.sort_key.asc().nullslast(),
                MovieItem.title.asc(),
                MovieItem.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(statement)
        return [_response(item) for item in result.scalars().unique()]

    async def get(self, item_id: UUID) -> CatalogMovieItemResponse:
        result = await self.db.execute(select(MovieItem).where(MovieItem.id == item_id))
        item = result.scalar_one_or_none()
        if item is None:
            raise ApiHTTPException(
                status_code=404,
                code="movie_item_not_found",
                detail="Movie Catalog Item not found",
            )
        return _response(item)


def _response(item: MovieItem) -> CatalogMovieItemResponse:
    fields = dict(item.details)
    fields["title"] = item.title
    fields["sort_key"] = item.sort_key
    fields["barcode"] = item.barcode
    fields["catalog_number"] = item.catalog_number
    fields["media"] = item.details.get("media", [])
    return CatalogMovieItemResponse.model_validate(
        {
            "id": item.id,
            "kind": "movie",
            "revision": item.revision,
            **fields,
        }
    )


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _optional_integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _contained_media(values: Any) -> list[dict[str, Any]]:
    media: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    if not isinstance(values, list):
        return media
    for value in values:
        if not isinstance(value, dict):
            continue
        media_number = _optional_integer(value.get("media_number"))
        if media_number is None or media_number < 1:
            raise ValueError("Movie media_number must be a positive integer")
        if media_number in seen_numbers:
            raise ValueError("Movie media numbers must be unique within a Catalog Item")
        seen_numbers.add(media_number)
        item = dict(value)
        try:
            item_id = UUID(str(item.get("id"))) if item.get("id") else uuid4()
        except ValueError as error:
            raise ValueError("Movie media id must be a UUID") from error
        item["id"] = str(item_id)
        item["media_number"] = media_number
        media.append(item)
    return sorted(media, key=lambda item: item["media_number"])


def _normalize_identifiers(values: Any) -> list[dict[str, Any]]:
    """Normalize Movie identifiers for exact, GIN-indexed lookup."""
    if not isinstance(values, list):
        return []
    identifiers: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        if isinstance(value, str):
            identifier_type = "other"
            raw_value = value.strip()
            supplied_normalized = None
            supplied_id = None
            is_primary = False
        elif isinstance(value, Mapping):
            identifier_type = _optional_string(value.get("identifier_type")) or "other"
            raw_value = _optional_string(value.get("value")) or ""
            supplied_normalized = _optional_string(value.get("normalized_value"))
            supplied_id = value.get("id")
            is_primary = value.get("is_primary") is True
        else:
            continue
        if not raw_value:
            continue
        normalized = supplied_normalized or re.sub(r"[^a-z0-9]", "", raw_value.casefold())
        identity = identifier_type, normalized
        if identity in seen:
            raise ValueError("Movie identifiers must be unique by type and normalized value")
        seen.add(identity)
        try:
            identifier_id = str(UUID(str(supplied_id))) if supplied_id else str(uuid4())
        except ValueError as error:
            raise ValueError("Movie identifier id must be a UUID") from error
        identifiers.append(
            {
                "id": identifier_id,
                "identifier_type": identifier_type,
                "value": raw_value,
                "normalized_value": normalized,
                "is_primary": is_primary,
            }
        )
    return identifiers
