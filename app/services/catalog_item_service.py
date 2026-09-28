from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Text, and_, cast, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiHTTPException
from app.models.canonical_catalog_item_identities import CanonicalCatalogItemIdentity
from app.models.canonical_catalog_items import CanonicalCatalogItem
from app.schemas.catalog_item_v1 import (
    CATALOG_ITEM_DETAILS_BY_KIND,
    CatalogItemSummaryV1,
    CatalogItemV1,
    CatalogItemWriteV1,
)


class CatalogItemService:
    """Source-neutral CRUD and search for concrete catalog items."""

    _UNIQUE_IDENTIFIER_TYPES = frozenset(
        {"barcode", "ean", "gtin", "isbn", "isbn10", "isbn13", "upc"}
    )

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
        identity_keys = _canonical_identity_keys(details.kind, values)
        existing_ids = await self._identity_owners(details.kind, identity_keys)
        if existing_ids:
            raise self._identity_conflict(existing_ids)

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
        self.db.add_all(
            CanonicalCatalogItemIdentity(
                kind=details.kind,
                identifier_type=identifier_type,
                normalized_value=normalized_value,
                catalog_item_id=item.id,
            )
            for identifier_type, normalized_value in identity_keys
        )
        try:
            await self.db.flush()
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            existing_ids = await self._identity_owners(details.kind, identity_keys)
            if existing_ids:
                raise self._identity_conflict(existing_ids) from error
            raise ApiHTTPException(
                status_code=409,
                code="catalog_item_identifier_conflict",
                detail="A canonical identifier is already assigned to another Catalog Item.",
            ) from error
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
        identity_keys = _canonical_identity_keys(details.kind, values)
        existing_ids = await self._identity_owners(
            details.kind,
            identity_keys,
            excluding=item_id,
        )
        if existing_ids:
            raise ApiHTTPException(
                status_code=409,
                code="catalog_item_identifier_conflict",
                detail="A canonical identifier is already assigned to another Catalog Item.",
            )

        item.title = details.title.strip()
        item.sort_title = details.sort_title
        item.identifier_search = _identifier_search_text(values)
        item.details = values
        await self.db.execute(
            delete(CanonicalCatalogItemIdentity).where(
                CanonicalCatalogItemIdentity.catalog_item_id == item_id
            )
        )
        self.db.add_all(
            CanonicalCatalogItemIdentity(
                kind=details.kind,
                identifier_type=identifier_type,
                normalized_value=normalized_value,
                catalog_item_id=item.id,
            )
            for identifier_type, normalized_value in identity_keys
        )
        try:
            await self.db.flush()
            await self.db.commit()
        except IntegrityError as error:
            await self.db.rollback()
            raise ApiHTTPException(
                status_code=409,
                code="catalog_item_identifier_conflict",
                detail="A canonical identifier is already assigned to another Catalog Item.",
            ) from error
        return self._response(item)

    async def _identity_owners(
        self,
        kind: str,
        identity_keys: set[tuple[str, str]],
        *,
        excluding: UUID | None = None,
    ) -> set[UUID]:
        if not identity_keys:
            return set()
        matches = [
            and_(
                CanonicalCatalogItemIdentity.identifier_type == identifier_type,
                CanonicalCatalogItemIdentity.normalized_value == normalized_value,
            )
            for identifier_type, normalized_value in identity_keys
        ]
        statement = select(CanonicalCatalogItemIdentity.catalog_item_id).where(
            CanonicalCatalogItemIdentity.kind == kind,
            or_(*matches),
        )
        if excluding is not None:
            statement = statement.where(CanonicalCatalogItemIdentity.catalog_item_id != excluding)
        return set((await self.db.scalars(statement)).all())

    @staticmethod
    def _identity_conflict(item_ids: set[UUID]) -> ApiHTTPException:
        detail = (
            "A Catalog Item with one of these canonical identifiers already exists. "
            "Search for and select the existing item before adding copies."
        )
        if len(item_ids) > 1:
            detail = (
                "The submitted identifiers match multiple existing Catalog Items. "
                "Resolve the matches before creating another item."
            )
        return ApiHTTPException(
            status_code=409,
            code="catalog_item_identifier_conflict",
            detail=detail,
        )

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
            artist=_first_name(item.details.get("artists")),
            format=_nonempty_string(item.details.get("format")),
            country=_nonempty_string(item.details.get("country")),
            label=_first_name(item.details.get("labels")),
            barcode=_summary_barcode(item.details),
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


def _first_name(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    for entry in value:
        if isinstance(entry, dict):
            name = _nonempty_string(entry.get("name"))
            if name is not None:
                return name
    return None


def _nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _summary_barcode(details: dict[str, Any]) -> str | None:
    direct = _nonempty_string(details.get("barcode"))
    if direct is not None:
        return direct
    identifiers = details.get("identifiers")
    if not isinstance(identifiers, list):
        return None
    for identifier in identifiers:
        if not isinstance(identifier, dict):
            continue
        identifier_type = _nonempty_string(identifier.get("identifier_type"))
        value = _nonempty_string(identifier.get("value"))
        if identifier_type is not None and identifier_type.casefold() == "barcode":
            return value
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


def _canonical_identity_keys(
    kind: str,
    details: dict[str, Any],
) -> set[tuple[str, str]]:
    """Return normalized edition identifiers that are globally identifying."""
    keys: set[tuple[str, str]] = set()

    def add(identifier_type: object, value: object) -> None:
        if not isinstance(identifier_type, str) or not isinstance(value, str):
            return
        normalized_type = identifier_type.strip().casefold().replace("-", "").replace("_", "")
        if normalized_type not in CatalogItemService._UNIQUE_IDENTIFIER_TYPES:
            return
        normalized_value = _normalize_identifier(value)
        if normalized_value:
            keys.add((normalized_type, normalized_value))

    if kind == "music":
        add("barcode", details.get("barcode"))

    identifiers = details.get("identifiers")
    if isinstance(identifiers, list):
        for identifier in identifiers:
            if isinstance(identifier, dict):
                add(identifier.get("identifier_type"), identifier.get("value"))
    return keys


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())
