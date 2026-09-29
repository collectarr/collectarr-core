"""Read and write operations for flattened Book Catalog Items."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.canonical_support import Person
from app.models.catalog_book_item import (
    BookItem,
    BookItemCredit,
    BookItemIdentifier,
    BookItemPrinting,
)
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
        person_ids = {credit.person_id for credit in credits if credit.person_id is not None}
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
        identifier_keys = {
            (row.identifier_type, row.normalized_value or _normalize(row.value))
            for row in identifier_rows
        }
        if len(identifier_keys) != len(identifier_rows):
            raise ValueError("Book identifiers must be unique by type and normalized value")
        item = BookItem(
            title=title.strip(),
            sort_key=_optional_string(payload.get("sort_key")),
            barcode=_optional_string(payload.get("barcode")),
            catalog_number=_optional_string(payload.get("catalog_number")),
            details=payload,
            printings=[
                BookItemPrinting(
                    printing_number=_optional_integer(value.get("printing_number")),
                    title=_optional_string(value.get("title")),
                    release_date=_date_value(value.get("release_date")),
                    publisher=_optional_string(value.get("publisher")),
                    language=_optional_string(value.get("language")),
                    isbn=_optional_string(value.get("isbn")),
                )
                for value in printings
            ],
            credits=credits,
            identifiers=identifier_rows,
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
        statement = select(BookItem).options(
            selectinload(BookItem.printings),
            selectinload(BookItem.credits),
            selectinload(BookItem.identifiers),
        )
        if barcode and barcode.strip():
            exact = barcode.strip()
            statement = statement.where(
                or_(
                    BookItem.barcode == exact,
                    BookItem.identifiers.any(
                        or_(
                            BookItemIdentifier.value == exact,
                            BookItemIdentifier.normalized_value == _normalize(exact),
                        )
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
                    BookItem.identifiers.any(
                        or_(
                            BookItemIdentifier.value == term,
                            BookItemIdentifier.normalized_value == _normalize(term),
                        )
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
            .options(
                selectinload(BookItem.printings),
                selectinload(BookItem.credits),
                selectinload(BookItem.identifiers),
            )
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
    fields.update(
        {
            "title": item.title,
            "sort_key": item.sort_key,
            "barcode": item.barcode,
            "catalog_number": item.catalog_number,
            "printings": [
                {
                    "id": row.id,
                    "printing_number": row.printing_number,
                    "title": row.title,
                    "release_date": row.release_date,
                    "publisher": row.publisher,
                    "language": row.language,
                    "isbn": row.isbn,
                }
                for row in item.printings
            ],
            "creators": [
                _credit_response(row)
                for row in item.credits
                if row.credit_type == "creator"
            ],
            "contributors": [
                _credit_response(row)
                for row in item.credits
                if row.credit_type == "contributor"
            ],
            "identifiers": [
                {
                    "id": row.id,
                    "identifier_type": row.identifier_type,
                    "value": row.value,
                    "normalized_value": row.normalized_value,
                    "is_primary": row.is_primary,
                }
                for row in item.identifiers
            ],
        }
    )
    return CatalogBookItemResponse.model_validate(
        {"id": item.id, "kind": "book", "revision": item.revision, **fields}
    )


def _credit_response(row: BookItemCredit) -> dict[str, Any]:
    return {
        "id": row.id,
        "person_id": row.person_id,
        "name": row.name,
        "role": row.role,
        "role_id": row.role_id,
        "sequence": row.sequence,
    }


def _credit(credit_type: str, value: Any) -> BookItemCredit | None:
    if isinstance(value, str):
        name = value.strip()
        if not name:
            return None
        return BookItemCredit(credit_type=credit_type, name=name)
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
    return BookItemCredit(
        credit_type=credit_type,
        person_id=person_id,
        name=name,
        role=_optional_string(value.get("role")),
        role_id=_optional_string(value.get("role_id")),
        sequence=_optional_integer(value.get("sequence")),
    )


def _identifier(value: Any) -> BookItemIdentifier | None:
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
    return BookItemIdentifier(
        identifier_type=identifier_type,
        value=raw_value,
        normalized_value=normalized_value or None,
        is_primary=is_primary,
    )


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
