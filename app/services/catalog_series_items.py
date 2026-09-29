"""Read and write flattened Anime and TV Catalog Items."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.catalog_anime_item import (
    AnimeItem,
    AnimeItemEpisode,
    AnimeItemIdentifier,
    AnimeItemMedia,
)
from app.models.catalog_tv_item import (
    TvItem,
    TvItemEpisode,
    TvItemIdentifier,
    TvItemMedia,
    TvItemSeason,
)
from app.schemas.catalog_anime_item import CatalogAnimeItemResponse
from app.schemas.catalog_tv_item import CatalogTvItemResponse


class _CatalogSeriesItemService:
    kind: ItemKind
    item_model: Any
    episode_model: Any
    identifier_model: Any
    media_model: Any
    response_model: Any
    error_code: str
    error_label: str
    season_model: Any | None = None

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_from_proposal(self, submitted: dict[str, Any]) -> Any:
        payload = validate_catalog_item_payload(self.kind, submitted)
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{self.error_label} Catalog Item title must not be empty")

        media_payload = payload.pop("media", None) or []
        episode_payload = payload.pop("episodes", None) or []
        season_payload = payload.pop("seasons", None) or []
        identifiers = [
            identifier
            for identifier in (
                _identifier(self.identifier_model, value) for value in payload.pop("identifiers", None) or []
            )
            if identifier is not None
        ]
        identifier_keys = {
            (row.identifier_type, row.normalized_value) for row in identifiers
        }
        if len(identifier_keys) != len(identifiers):
            raise ValueError(f"{self.error_label} identifiers must be unique by type and value")

        season_rows: list[Any] = []
        nested_episodes: list[dict[str, Any]] = []
        seen_season_numbers: set[int] = set()
        if self.season_model is not None:
            for index, value in enumerate(season_payload):
                if not isinstance(value, dict):
                    continue
                season_details = dict(value)
                nested = season_details.pop("episodes", None) or []
                nested_episodes.extend(
                    episode for episode in nested if isinstance(episode, dict)
                )
                season_number = _integer(value.get("season_number"))
                season_number = season_number if season_number is not None else index + 1
                if season_number in seen_season_numbers:
                    raise ValueError("TV season numbers must be unique within a Catalog Item")
                seen_season_numbers.add(season_number)
                season_rows.append(
                    self.season_model(
                        season_number=season_number,
                        title=_optional_string(value.get("title")),
                        details=season_details,
                    )
                )
        if not episode_payload:
            episode_payload = nested_episodes

        episode_rows: list[Any] = []
        seen_episode_positions: set[int] = set()
        for index, value in enumerate(episode_payload):
            if not isinstance(value, dict):
                continue
            position = _integer(value.get("position"))
            position = position if position is not None else index
            if position in seen_episode_positions:
                raise ValueError("Episode positions must be unique within a Catalog Item")
            seen_episode_positions.add(position)
            episode_rows.append(
                self.episode_model(
                    position=position,
                    season_number=_integer(value.get("season_number"))
                    if self.kind is ItemKind.tv
                    else None,
                    episode_number=_integer(value.get("episode_number")),
                    title=_optional_string(value.get("episode_title"))
                    or _optional_string(value.get("title")),
                    details=value,
                )
            )

        item = self.item_model(
            title=title.strip(),
            sort_key=_optional_string(payload.pop("sort_key", None)),
            barcode=_optional_string(payload.pop("barcode", None)),
            catalog_number=_optional_string(payload.pop("catalog_number", None)),
            details=payload,
            media=[
                self.media_model(
                    position=index,
                    media_number=_integer(
                        value.get("media_number", value.get("disc_number", value.get("medium_number")))
                    ),
                    details=value,
                )
                for index, value in enumerate(media_payload)
                if isinstance(value, dict)
            ],
            episodes=episode_rows,
            identifiers=identifiers,
            **({"seasons": season_rows} if self.season_model is not None else {}),
        )
        self.db.add(item)
        await self.db.flush()
        return _response(item, self.response_model, self.kind)

    async def search(
        self,
        *,
        query: str | None,
        barcode: str | None,
        limit: int,
        offset: int,
    ) -> list[Any]:
        statement = self._with_children(select(self.item_model))
        if barcode and barcode.strip():
            exact = barcode.strip()
            statement = statement.where(
                or_(
                    self.item_model.barcode == exact,
                    self.item_model.identifiers.any(
                        or_(
                            self.identifier_model.value == exact,
                            self.identifier_model.normalized_value == _normalize(exact),
                        )
                    ),
                )
            )
        elif query and query.strip():
            exact = query.strip()
            statement = statement.where(
                or_(
                    self.item_model.title.ilike(f"%{exact}%"),
                    self.item_model.sort_key.ilike(f"%{exact}%"),
                    self.item_model.barcode == exact,
                    self.item_model.catalog_number == exact,
                    self.item_model.identifiers.any(
                        self.identifier_model.normalized_value == _normalize(exact)
                    ),
                )
            )
        statement = (
            statement.order_by(
                self.item_model.sort_key.asc().nullslast(),
                self.item_model.title.asc(),
                self.item_model.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(statement)
        return [
            _response(item, self.response_model, self.kind)
            for item in result.scalars().unique()
        ]

    async def get(self, item_id: UUID) -> Any:
        statement = self._with_children(
            select(self.item_model).where(self.item_model.id == item_id)
        )
        result = await self.db.execute(statement)
        item = result.scalar_one_or_none()
        if item is None:
            raise ApiHTTPException(
                status_code=404,
                code=self.error_code,
                detail=f"{self.error_label} Catalog Item not found",
            )
        return _response(item, self.response_model, self.kind)

    def _with_children(self, statement: Any) -> Any:
        statement = statement.options(
            selectinload(self.item_model.media),
            selectinload(self.item_model.episodes),
            selectinload(self.item_model.identifiers),
        )
        if self.season_model is not None:
            statement = statement.options(selectinload(self.item_model.seasons))
        return statement


class CatalogAnimeItemService(_CatalogSeriesItemService):
    kind = ItemKind.anime
    item_model = AnimeItem
    media_model = AnimeItemMedia
    episode_model = AnimeItemEpisode
    identifier_model = AnimeItemIdentifier
    response_model = CatalogAnimeItemResponse
    error_code = "anime_item_not_found"
    error_label = "Anime"


class CatalogTvItemService(_CatalogSeriesItemService):
    kind = ItemKind.tv
    item_model = TvItem
    media_model = TvItemMedia
    episode_model = TvItemEpisode
    identifier_model = TvItemIdentifier
    season_model = TvItemSeason
    response_model = CatalogTvItemResponse
    error_code = "tv_item_not_found"
    error_label = "TV"


def _response(item: Any, response_model: Any, kind: ItemKind) -> Any:
    fields = dict(item.details)
    fields.update(
        {
            "id": item.id,
            "kind": kind.value,
            "title": item.title,
            "sort_key": item.sort_key,
            "barcode": item.barcode,
            "catalog_number": item.catalog_number,
            "revision": item.revision,
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
            "media": [
                {**row.details, "id": row.id, "media_number": row.media_number}
                for row in item.media
            ],
            "episodes": [
                {
                    **row.details,
                    "id": row.id,
                    "season_number": row.season_number,
                    "episode_number": row.episode_number,
                    "episode_title": row.title,
                    "title": row.title,
                }
                for row in item.episodes
            ],
        }
    )
    if kind is ItemKind.tv:
        episodes_by_season: dict[int | None, list[dict[str, Any]]] = {}
        for episode in fields["episodes"]:
            episodes_by_season.setdefault(episode.get("season_number"), []).append(episode)
        fields["seasons"] = [
            {
                **season.details,
                "id": season.id,
                "season_number": season.season_number,
                "title": season.title,
                "episodes": episodes_by_season.get(season.season_number, []),
            }
            for season in item.seasons
        ]
    return response_model.model_validate(fields)


def _identifier(model: Any, value: Any) -> Any | None:
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
    return model(
        identifier_type=identifier_type,
        value=raw_value,
        normalized_value=normalized_value,
        is_primary=is_primary,
    )


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
