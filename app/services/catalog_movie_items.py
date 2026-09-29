"""Read and write operations for flattened Movie Catalog Items."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.catalog_movie_item import MovieItem, MovieItemMedia
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

        media_payload = item_payload.pop("media", None) or []
        item = MovieItem(
            title=title.strip(),
            sort_key=_optional_string(item_payload.get("sort_key")),
            barcode=_optional_string(item_payload.get("barcode")),
            catalog_number=_optional_string(item_payload.get("catalog_number")),
            details=item_payload,
            media=[
                MovieItemMedia(
                    media_number=value["media_number"],
                    media_type=_optional_string(value.get("media_type")),
                    title=_optional_string(value.get("title")),
                    aspect_ratio=_optional_string(value.get("aspect_ratio")),
                    screen_ratio=_optional_string(value.get("screen_ratio")),
                    color=_optional_string(value.get("color")),
                    num_discs=_optional_integer(value.get("num_discs")),
                    nr_layers=_optional_integer(value.get("nr_layers")),
                    layers=_optional_string(value.get("layers")),
                    audio_tracks=_optional_string(value.get("audio_tracks")),
                    subtitles=_optional_string(value.get("subtitles")),
                )
                for value in media_payload
                if isinstance(value, dict)
            ],
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
        statement = select(MovieItem).options(selectinload(MovieItem.media))
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
        result = await self.db.execute(
            select(MovieItem)
            .where(MovieItem.id == item_id)
            .options(selectinload(MovieItem.media))
        )
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
    fields["media"] = [
        {
            "id": media.id,
            "media_number": media.media_number,
            "media_type": media.media_type,
            "title": media.title,
            "aspect_ratio": media.aspect_ratio,
            "screen_ratio": media.screen_ratio,
            "color": media.color,
            "num_discs": media.num_discs,
            "nr_layers": media.nr_layers,
            "layers": media.layers,
            "audio_tracks": media.audio_tracks,
            "subtitles": media.subtitles,
        }
        for media in item.media
    ]
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

