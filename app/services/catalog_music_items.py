"""Read/search operations for flattened Music catalog items."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.catalog_music_item import MusicItem
from app.models.partial_date import PartialDateValue
from app.schemas.catalog_music_item import (
    CatalogMusicItemResponse,
    CatalogMusicItemSearchPage,
)


class CatalogMusicItemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_from_proposal(self, payload: dict[str, Any]) -> CatalogMusicItemResponse:
        """Publish an approved Music Add/Edit payload as one flat root item."""
        item_payload = validate_catalog_item_payload(ItemKind.music, payload)
        title = item_payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Music Catalog Item title must not be empty")

        credits = {
            key: _credit_objects(item_payload.get(key))
            for key in (
                "artist_credits",
                "composers",
                "conductors",
                "songwriters",
                "producers",
                "engineers",
                "musicians",
            )
        }
        artist = (
            _optional_string(item_payload.get("artist"))
            or "".join(
                f"{credit['name']}{credit.get('join_phrase') or ''}"
                for credit in credits["artist_credits"]
            ).strip()
            or None
        )
        item = MusicItem(
            title=title.strip(),
            sort_title=_optional_string(item_payload.get("sort_title")),
            subtitle=_optional_string(item_payload.get("subtitle")),
            artist=artist,
            artist_credits=credits["artist_credits"],
            original_release_date=_partial_date(item_payload.get("original_release_date")),
            recording_date=_partial_date(item_payload.get("recording_date")),
            release_date=_partial_date(item_payload.get("release_date")),
            label=_optional_string(item_payload.get("label")),
            barcode=_optional_string(item_payload.get("barcode")),
            catalog_number=_optional_string(item_payload.get("catalog_number")),
            genres=_string_values(item_payload.get("genres")),
            packaging=_optional_string(item_payload.get("packaging")),
            studios=_string_values(item_payload.get("studios")),
            country=_optional_string(item_payload.get("country")),
            is_live=item_payload.get("is_live")
            if isinstance(item_payload.get("is_live"), bool)
            else None,
            extra=_optional_string(item_payload.get("extra")),
            spars_code=_optional_string(item_payload.get("spars_code")),
            box_set=_optional_string(item_payload.get("box_set")),
            composers=credits["composers"],
            conductors=credits["conductors"],
            choruses=_string_values(item_payload.get("choruses")),
            compositions=_string_values(item_payload.get("compositions")),
            orchestras=_string_values(item_payload.get("orchestras")),
            songwriters=credits["songwriters"],
            producers=credits["producers"],
            engineers=credits["engineers"],
            musicians=credits["musicians"],
            external_links=_object_values(item_payload.get("external_links")),
            cover_image_url=_optional_string(item_payload.get("cover_image_url")),
            back_cover_image_url=_optional_string(item_payload.get("back_cover_image_url")),
            thumbnail_image_url=_optional_string(item_payload.get("thumbnail_image_url")),
            discs=item_payload.get("discs") or [],
        )
        self.db.add(item)
        await self.db.flush()
        return CatalogMusicItemResponse.model_validate(item)

    async def search(
        self,
        *,
        query: str | None,
        barcode: str | None,
        artist: str | None = None,
        label: str | None = None,
        subtitle: str | None = None,
        country: str | None = None,
        catalog_number: str | None = None,
        year: int | None = None,
        limit: int,
        offset: int,
    ) -> CatalogMusicItemSearchPage:
        stmt = select(MusicItem)
        if barcode and barcode.strip():
            stmt = stmt.where(MusicItem.barcode == barcode.strip())
        elif query and query.strip():
            term = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    MusicItem.title.ilike(term),
                    MusicItem.artist.ilike(term),
                    MusicItem.subtitle.ilike(term),
                    MusicItem.label.ilike(term),
                    MusicItem.catalog_number == query.strip(),
                    MusicItem.barcode == query.strip(),
                )
            )
        if artist and artist.strip():
            stmt = stmt.where(MusicItem.artist.ilike(f"%{artist.strip()}%"))
        if label and label.strip():
            stmt = stmt.where(MusicItem.label.ilike(f"%{label.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(MusicItem.subtitle.ilike(f"%{subtitle.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(MusicItem.country.ilike(f"%{country.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(MusicItem.catalog_number == catalog_number.strip())
        if year is not None:
            stmt = stmt.where(
                or_(
                    MusicItem.release_date["year"].as_integer() == year,
                    MusicItem.original_release_date["year"].as_integer() == year,
                    MusicItem.recording_date["year"].as_integer() == year,
                )
            )
        stmt = (
            stmt.order_by(
                MusicItem.sort_title.asc().nullslast(),
                MusicItem.title.asc(),
                MusicItem.id.asc(),
            )
            .offset(offset)
            .limit(limit + 1)
        )
        result = await self.db.execute(stmt)
        rows = list(result.scalars().unique())
        has_more = len(rows) > limit
        rows = rows[:limit]
        return CatalogMusicItemSearchPage(
            items=[CatalogMusicItemResponse.model_validate(item) for item in rows],
            next_offset=offset + len(rows) if has_more else None,
            has_more=has_more,
        )

    async def get(self, item_id: UUID) -> CatalogMusicItemResponse:
        result = await self.db.execute(select(MusicItem).where(MusicItem.id == item_id))
        item = result.scalar_one_or_none()
        if item is None:
            raise ApiHTTPException(
                status_code=404,
                code="music_item_not_found",
                detail="Music Catalog Item not found",
            )
        return CatalogMusicItemResponse.model_validate(item)


def _credit_objects(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return result
    for entry in value:
        if isinstance(entry, str) and entry.strip():
            result.append({"id": str(uuid4()), "name": entry.strip()})
        elif isinstance(entry, dict):
            name = entry.get("name") or entry.get("credited_name")
            if isinstance(name, str) and name.strip():
                credit = {
                    key: part
                    for key, part in entry.items()
                    if key
                    in {
                        "id",
                        "artist_id",
                        "role",
                        "role_id",
                        "sequence",
                        "credited_name",
                        "join_phrase",
                        "instrument",
                    }
                }
                raw_id = credit.get("id")
                try:
                    credit["id"] = str(UUID(str(raw_id))) if raw_id else str(uuid4())
                except ValueError as error:
                    raise ValueError("Music credit id must be a UUID") from error
                credit["name"] = name.strip()
                result.append(credit)
    return result


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]


def _object_values(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(entry) for entry in value if isinstance(entry, dict)]


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _partial_date(value: Any) -> dict[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Music dates must be partial-date objects")
    parsed = PartialDateValue.model_validate(value)
    return None if parsed.is_empty else parsed.model_dump(exclude_none=True)
