"""Persistence/search mechanics for flat, independently registered inventories."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind


class FlatInventoryItemService[ResponseT: BaseModel]:
    model: type[Any]
    response_model: type[ResponseT]
    kind: ItemKind

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _response(self, item: Any) -> ResponseT:
        return self.response_model.model_validate({
            **item.details, "id": item.id, "kind": self.kind.value,
            "title": item.title, "sort_key": item.sort_key,
            "barcode": item.barcode, "revision": item.revision,
        })

    async def create_from_proposal(self, submitted: dict[str, Any]) -> ResponseT:
        payload = validate_catalog_item_payload(self.kind, submitted)
        title = payload.pop("title", "")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Catalog Item title must not be empty")
        item = self.model(
            title=title.strip(), sort_key=payload.pop("sort_key", None),
            barcode=payload.pop("barcode", None), details=payload,
        )
        self.db.add(item)
        await self.db.flush()
        return self._response(item)

    async def search(self, *, query: str | None, barcode: str | None,
                     limit: int, offset: int) -> list[ResponseT]:
        model = self.model
        statement = select(model)
        if barcode and barcode.strip():
            statement = statement.where(model.barcode == barcode.strip())
        elif query and query.strip():
            term = f"%{query.strip()}%"
            statement = statement.where(or_(model.title.ilike(term), model.sort_key.ilike(term)))
        result = await self.db.execute(statement.order_by(
            model.sort_key.asc().nullslast(), model.title.asc(), model.id.asc(),
        ).offset(offset).limit(limit))
        return [self._response(item) for item in result.scalars().unique()]

    async def get(self, item_id: UUID) -> ResponseT:
        result = await self.db.execute(select(self.model).where(self.model.id == item_id))
        item = result.scalar_one_or_none()
        if item is None:
            raise ApiHTTPException(status_code=404, code=f"{self.kind.value}_item_not_found",
                                   detail="Catalog Item not found")
        return self._response(item)
