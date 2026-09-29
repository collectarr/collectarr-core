"""Read/search operations for flattened Music catalog items."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import extract, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.catalog_music_item import MusicItem, MusicItemDisc, MusicItemTrack
from app.schemas.catalog_music_item import CatalogMusicItemResponse


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
            original_release_date=_partial_date(
                item_payload.get("original_release_date_parts")
                or item_payload.get("original_release_date")
            ),
            original_release_date_parts=item_payload.get("original_release_date_parts")
            or item_payload.get("original_release_date"),
            recording_date=_partial_date(
                item_payload.get("recording_date_parts") or item_payload.get("recording_date")
            ),
            recording_date_parts=item_payload.get("recording_date_parts")
            or item_payload.get("recording_date"),
            release_date=_partial_date(
                item_payload.get("release_date_parts") or item_payload.get("release_date")
            ),
            release_date_parts=item_payload.get("release_date_parts")
            or item_payload.get("release_date"),
            label=_optional_string(item_payload.get("label")),
            format=_optional_string(item_payload.get("format")),
            barcode=_optional_string(item_payload.get("barcode")),
            catalog_number=_optional_string(item_payload.get("catalog_number")),
            genres=_string_values(item_payload.get("genres")),
            packaging=_optional_string(item_payload.get("packaging")),
            studios=_string_values(item_payload.get("studios")),
            country=_optional_string(item_payload.get("country")),
            is_live=item_payload.get("is_live")
            if isinstance(item_payload.get("is_live"), bool)
            else None,
            sound_types=_string_values(item_payload.get("sound_types")),
            vinyl_color=_optional_string(item_payload.get("vinyl_color")),
            vinyl_weight=_optional_string(item_payload.get("vinyl_weight")),
            rpm=item_payload.get("rpm") if isinstance(item_payload.get("rpm"), int) else None,
            extra=_optional_string(item_payload.get("extra")),
            spars=_optional_string(item_payload.get("spars")),
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
            discs=[],
        )
        for disc_index, disc_payload in enumerate(
            _object_values(item_payload.get("discs")), start=1
        ):
            disc_number = disc_payload.get("disc_number")
            disc = MusicItemDisc(
                disc_number=disc_number if isinstance(disc_number, int) else disc_index,
                title=_optional_string(disc_payload.get("title")),
                matrix_number_side_a=_optional_string(disc_payload.get("matrix_number_side_a")),
                matrix_number_side_b=_optional_string(disc_payload.get("matrix_number_side_b")),
                tracks=[],
            )
            for position_order, track_payload in enumerate(
                _object_values(disc_payload.get("tracks"))
            ):
                position = track_payload.get("position")
                disc.tracks.append(
                    MusicItemTrack(
                        position=str(position if position is not None else position_order + 1),
                        position_order=position_order,
                        title=str(track_payload.get("title") or "").strip(),
                        artist=_optional_string(track_payload.get("artist")),
                        duration_ms=track_payload.get("duration_ms")
                        if isinstance(track_payload.get("duration_ms"), int)
                        else None,
                    )
                )
            item.discs.append(disc)

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
    ) -> list[CatalogMusicItemResponse]:
        stmt = select(MusicItem).options(
            selectinload(MusicItem.discs).selectinload(MusicItemDisc.tracks)
        )
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
                    MusicItem.catalog_number.ilike(term),
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
            stmt = stmt.where(
                MusicItem.catalog_number.ilike(f"%{catalog_number.strip()}%")
            )
        if year is not None:
            stmt = stmt.where(
                or_(
                    extract("year", MusicItem.release_date) == year,
                    extract("year", MusicItem.original_release_date) == year,
                    extract("year", MusicItem.recording_date) == year,
                )
            )
        stmt = (
            stmt.order_by(
                MusicItem.sort_title.asc().nullslast(), MusicItem.title.asc(), MusicItem.id.asc()
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [CatalogMusicItemResponse.model_validate(item) for item in result.scalars().unique()]

    async def get(self, item_id: UUID) -> CatalogMusicItemResponse:
        result = await self.db.execute(
            select(MusicItem)
            .where(MusicItem.id == item_id)
            .options(selectinload(MusicItem.discs).selectinload(MusicItemDisc.tracks))
        )
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
            result.append({"name": entry.strip()})
        elif isinstance(entry, dict):
            name = entry.get("name") or entry.get("credited_name")
            if isinstance(name, str) and name.strip():
                credit = {
                    key: part
                    for key, part in entry.items()
                    if key
                    in {
                        "role",
                        "role_id",
                        "sequence",
                        "credited_name",
                        "join_phrase",
                        "instrument",
                    }
                }
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


def _partial_date(value: Any) -> date | None:
    if isinstance(value, dict):
        year, month, day = value.get("year"), value.get("month"), value.get("day")
        if isinstance(year, int) and isinstance(month, int) and isinstance(day, int):
            try:
                return date(year, month, day)
            except ValueError:
                return None
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None
