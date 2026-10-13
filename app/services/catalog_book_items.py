"""Read and write operations for flattened Book Catalog Items."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.canonical_support import Person
from app.models.catalog_book_item import (
    BookItem,
)
from app.models.catalog_book_series import BookSeries
from app.schemas.catalog_book_item import CatalogBookItemResponse


class CatalogBookItemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_from_proposal(
        self,
        submitted: dict[str, Any],
    ) -> CatalogBookItemResponse:
        payload = validate_catalog_item_payload(ItemKind.book, submitted)
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Book Catalog Item title must not be empty")

        printings = payload.pop("printings", None) or []
        creators = payload.pop("creators", None) or []
        contributors = payload.pop("contributors", None) or []
        identifiers = payload.pop("identifiers", None) or []
        credits = [
            credit
            for credit in (_credit("creator", value) for value in creators)
            if credit is not None
        ] + [
            credit
            for credit in (_credit("contributor", value) for value in contributors)
            if credit is not None
        ]
        person_ids = {
            UUID(credit["person_id"])
            for credit in credits
            if credit.get("person_id") is not None
        }
        if person_ids:
            result = await self.db.execute(select(Person.id).where(Person.id.in_(person_ids)))
            found_person_ids = set(result.scalars())
            missing_person_ids = person_ids - found_person_ids
            if missing_person_ids:
                raise ValueError(
                    "Book credit person_id does not refer to a known catalog person: "
                    + ", ".join(sorted(str(value) for value in missing_person_ids))
                )
        identifier_rows = [
            identifier
            for identifier in (_identifier(value) for value in identifiers)
            if identifier is not None
        ]
        for key in ("isbn", "isbn10", "isbn13"):
            value = _optional_string(payload.get(key))
            if value is not None:
                candidate = _identifier(
                    {"identifier_type": key, "value": value}
                )
                if candidate is not None:
                    identifier_rows.append(candidate)
        for printing in printings:
            if not isinstance(printing, dict):
                continue
            value = _optional_string(printing.get("isbn"))
            if value is None:
                continue
            candidate = _identifier({"identifier_type": "isbn", "value": value})
            if candidate is not None:
                identifier_rows.append(candidate)
        identifiers_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for row in identifier_rows:
            identity = row["identifier_type"], row["normalized_value"]
            existing = identifiers_by_key.get(identity)
            if existing is None:
                identifiers_by_key[identity] = row
            elif existing["value"] != row["value"]:
                raise ValueError("Book identifiers must be unique by type and normalized value")
        identifier_rows = list(identifiers_by_key.values())
        raw_memberships = payload.pop("series_memberships", None) or []
        series_memberships: list[dict[str, Any]] = []
        for value in raw_memberships:
            if not isinstance(value, dict):
                continue
            try:
                series_id = UUID(str(value.get("series_id")))
            except (TypeError, ValueError) as error:
                raise ValueError("Book series_id must be a UUID") from error
            exists = await self.db.scalar(
                select(BookSeries.id).where(BookSeries.id == series_id)
            )
            if exists is None:
                raise ValueError(f"Book series_id does not refer to a known series: {series_id}")
            membership_id = _component_id(value.get("id"), "Book series membership")
            series_memberships.append(
                {
                    "id": membership_id,
                    "series_id": str(series_id),
                    "sequence": _optional_number(value.get("sequence")),
                    "display_number": _optional_string(value.get("display_number")),
                }
            )
        series_title = _optional_string(payload.get("series_title"))
        if series_title is not None:
            series_result = await self.db.execute(
                select(BookSeries).where(
                    func.lower(BookSeries.title) == series_title.casefold()
                ).limit(1)
            )
            series = series_result.scalar_one_or_none()
            if series is None:
                series = BookSeries(title=series_title, slug=_normalize(series_title))
                self.db.add(series)
                await self.db.flush()
            if not any(value["series_id"] == str(series.id) for value in series_memberships):
                series_memberships.append(
                    {
                        "id": str(uuid4()),
                        "series_id": str(series.id),
                        "sequence": _optional_number(payload.get("volume_number")),
                        "display_number": _optional_string(payload.get("volume_number")),
                    }
                )
        contained_printings = [_printing(value) for value in printings]
        contained_printings = [value for value in contained_printings if value is not None]
        details = {
            **payload,
            "printings": contained_printings,
            "credits": credits,
            "identifiers": identifier_rows,
            "series_memberships": series_memberships,
        }
        item = BookItem(
            title=title.strip(),
            sort_key=_optional_string(payload.get("sort_key")),
            barcode=_optional_string(payload.get("barcode")),
            catalog_number=_optional_string(payload.get("catalog_number")),
            details=details,
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
    ) -> list[CatalogBookItemResponse]:
        statement = select(BookItem)
        if barcode and barcode.strip():
            exact = barcode.strip()
            statement = statement.where(
                or_(
                    BookItem.barcode == exact,
                    BookItem.details.contains(
                        {"identifiers": [{"normalized_value": _normalize(exact)}]}
                    ),
                )
            )
        elif query and query.strip():
            term = query.strip()
            statement = statement.where(
                or_(
                    BookItem.title.ilike(f"%{term}%"),
                    BookItem.sort_key.ilike(f"%{term}%"),
                    BookItem.barcode == term,
                    BookItem.catalog_number == term,
                    BookItem.details.contains(
                        {"identifiers": [{"normalized_value": _normalize(term)}]}
                    ),
                )
            )
        statement = (
            statement.order_by(
                BookItem.sort_key.asc().nullslast(),
                BookItem.title.asc(),
                BookItem.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(statement)
        return [_response(item) for item in result.scalars().unique()]

    async def get(self, item_id: UUID) -> CatalogBookItemResponse:
        result = await self.db.execute(
            select(BookItem)
            .where(BookItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise ApiHTTPException(
                status_code=404,
                code="book_item_not_found",
                detail="Book Catalog Item not found",
            )
        return _response(item)


def _response(item: BookItem) -> CatalogBookItemResponse:
    fields = dict(item.details)
    credits = fields.pop("credits", [])
    fields.update(
        {
            "title": item.title,
            "sort_key": item.sort_key,
            "barcode": item.barcode,
            "catalog_number": item.catalog_number,
            "printings": fields.get("printings", []),
            "creators": [
                _credit_response(row) for row in credits if row.get("credit_type") == "creator"
            ],
            "contributors": [
                _credit_response(row) for row in credits if row.get("credit_type") == "contributor"
            ],
            "identifiers": fields.get("identifiers", []),
            "series_memberships": fields.get("series_memberships", []),
        }
    )
    return CatalogBookItemResponse.model_validate(
        {"id": item.id, "kind": "book", "revision": item.revision, **fields}
    )


def _credit_response(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def _credit(credit_type: str, value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        name = value.strip()
        if not name:
            return None
        return {"id": str(uuid4()), "credit_type": credit_type, "name": name}
    if not isinstance(value, dict):
        return None
    name = _optional_string(value.get("name"))
    if name is None:
        return None
    person_id = value.get("person_id")
    if person_id is not None:
        try:
            person_id = UUID(str(person_id))
        except ValueError as error:
            raise ValueError("Book credit person_id must be a UUID") from error
    try:
        credit_id = str(UUID(str(value.get("id")))) if value.get("id") else str(uuid4())
    except ValueError as error:
        raise ValueError("Book credit id must be a UUID") from error
    return {
        "id": credit_id,
        "credit_type": credit_type,
        "person_id": str(person_id) if person_id is not None else None,
        "name": name,
        "role": _optional_string(value.get("role")),
        "role_id": _optional_string(value.get("role_id")),
        "sequence": _optional_integer(value.get("sequence")),
    }


def _identifier(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        identifier_type = "other"
        raw_value = value.strip()
        normalized_value = _normalize(raw_value)
        is_primary = False
    elif isinstance(value, dict):
        identifier_type = _optional_string(value.get("identifier_type"))
        raw_value = _optional_string(value.get("value"))
        if identifier_type is None or raw_value is None:
            return None
        normalized_value = _optional_string(value.get("normalized_value")) or _normalize(
            raw_value
        )
        is_primary = value.get("is_primary") is True
    else:
        return None
    if not raw_value:
        return None
    try:
        identifier_id = str(UUID(str(value.get("id")))) if isinstance(value, dict) and value.get("id") else str(uuid4())
    except ValueError as error:
        raise ValueError("Book identifier id must be a UUID") from error
    return {
        "id": identifier_id,
        "identifier_type": identifier_type,
        "value": raw_value,
        "normalized_value": normalized_value or _normalize(raw_value),
        "is_primary": is_primary,
    }


def _printing(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    try:
        printing_id = str(UUID(str(value.get("id")))) if value.get("id") else str(uuid4())
    except ValueError as error:
        raise ValueError("Book printing id must be a UUID") from error
    return {
        "id": printing_id,
        "printing_number": _optional_integer(value.get("printing_number")),
        "title": _optional_string(value.get("title")),
        "release_date": _date_value(value.get("release_date")),
        "publisher": _optional_string(value.get("publisher")),
        "language": _optional_string(value.get("language")),
        "isbn": _optional_string(value.get("isbn")),
    }


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _optional_integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _date_value(value: Any) -> Any | None:
    if isinstance(value, str):
        return _optional_string(value)
    if isinstance(value, dict):
        return value or None
    return None


def _component_id(value: Any, label: str) -> str:
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(str(value)))
    except ValueError as error:
        raise ValueError(f"{label} id must be a UUID") from error


def _optional_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
