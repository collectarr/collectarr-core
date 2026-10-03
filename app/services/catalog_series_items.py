"""Read and write Anime and TV catalog documents with contained values."""

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
from app.models.catalog_anime_item import AnimeItem
from app.models.catalog_tv_item import TvItem
from app.schemas.catalog_anime_item import CatalogAnimeItemResponse
from app.schemas.catalog_tv_item import CatalogTvItemResponse


class _CatalogSeriesItemService:
    kind: ItemKind
    item_model: Any
    response_model: Any
    error_code: str
    error_label: str

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_from_proposal(self, submitted: dict[str, Any]) -> Any:
        payload = validate_catalog_item_payload(self.kind, submitted)
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{self.error_label} Catalog Item title must not be empty")

        raw_media = payload.get("media", []) or []
        raw_episodes = payload.get("episodes", []) or []
        raw_seasons = payload.get("seasons", []) or []
        raw_identifiers = payload.get("identifiers", []) or []

        seasons, nested_episodes = _normalize_seasons(raw_seasons)
        episode_source = raw_episodes or nested_episodes
        episodes = _normalize_episodes(episode_source, self.kind)
        media = _normalize_media(raw_media)
        identifiers = _normalize_identifiers(raw_identifiers, self.error_label)

        payload["media"] = media
        payload["episodes"] = episodes
        payload["identifiers"] = identifiers
        # Seasons are item-contained values for both series kinds. Anime may
        # omit them, but preserving a submitted season list avoids discarding
        # valid catalog details while normalizing its episodes.
        payload["seasons"] = seasons

        item = self.item_model(
            title=title.strip(),
            sort_key=_optional_string(payload.pop("sort_key", None)),
            barcode=_optional_string(payload.pop("barcode", None)),
            catalog_number=_optional_string(payload.pop("catalog_number", None)),
            details=payload,
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
        statement = select(self.item_model)
        if barcode and barcode.strip():
            exact = barcode.strip()
            statement = statement.where(
                or_(
                    self.item_model.barcode == exact,
                    self.item_model.details.contains(
                        {"identifiers": [{"normalized_value": _normalize(exact)}]}
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
                    self.item_model.details.contains(
                        {"identifiers": [{"normalized_value": _normalize(exact)}]}
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
        return [_response(item, self.response_model, self.kind) for item in result.scalars()]

    async def get(self, item_id: UUID) -> Any:
        result = await self.db.execute(
            select(self.item_model).where(self.item_model.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise ApiHTTPException(
                status_code=404,
                code=self.error_code,
                detail=f"{self.error_label} Catalog Item not found",
            )
        return _response(item, self.response_model, self.kind)


class CatalogAnimeItemService(_CatalogSeriesItemService):
    kind = ItemKind.anime
    item_model = AnimeItem
    response_model = CatalogAnimeItemResponse
    error_code = "anime_item_not_found"
    error_label = "Anime"


class CatalogTvItemService(_CatalogSeriesItemService):
    kind = ItemKind.tv
    item_model = TvItem
    response_model = CatalogTvItemResponse
    error_code = "tv_item_not_found"
    error_label = "TV"


def _response(item: Any, response_model: Any, kind: ItemKind) -> Any:
    fields = dict(item.details)
    if kind is ItemKind.tv:
        episodes_by_season: dict[int | None, list[dict[str, Any]]] = {}
        for episode in fields.get("episodes", []):
            episodes_by_season.setdefault(episode.get("season_number"), []).append(episode)
        fields["seasons"] = [
            {**season, "episodes": episodes_by_season.get(season["season_number"], [])}
            for season in fields.get("seasons", [])
        ]
    fields.update(
        {
            "id": item.id,
            "kind": kind.value,
            "title": item.title,
            "sort_key": item.sort_key,
            "barcode": item.barcode,
            "catalog_number": item.catalog_number,
            "revision": item.revision,
        }
    )
    return response_model.model_validate(fields)


def _normalize_seasons(values: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seasons: list[dict[str, Any]] = []
    nested_episodes: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    if not isinstance(values, list):
        return seasons, nested_episodes
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            continue
        season = dict(value)
        season_number = _integer(season.get("season_number"))
        season_number = season_number if season_number is not None else index + 1
        if season_number < 0 or season_number in seen_numbers:
            raise ValueError("TV season numbers must be unique non-negative integers")
        seen_numbers.add(season_number)
        nested = season.pop("episodes", []) or []
        if isinstance(nested, list):
            nested_episodes.extend(item for item in nested if isinstance(item, dict))
        season["id"] = _component_id(season.get("id"), "TV season")
        season["season_number"] = season_number
        seasons.append(season)
    return seasons, nested_episodes


def _normalize_episodes(values: Any, kind: ItemKind) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    seen_positions: set[int] = set()
    if not isinstance(values, list):
        return episodes
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            continue
        episode = dict(value)
        position = _integer(episode.get("position"))
        position = index if position is None else position
        if position < 0 or position in seen_positions:
            raise ValueError(f"{kind.value} episode positions must be unique non-negative integers")
        seen_positions.add(position)
        episode["id"] = _component_id(episode.get("id"), f"{kind.value} episode")
        episode["position"] = position
        if kind is ItemKind.tv:
            episode["season_number"] = _integer(episode.get("season_number"))
        episode["episode_number"] = _integer(episode.get("episode_number"))
        title = _optional_string(episode.get("episode_title")) or _optional_string(episode.get("title"))
        episode["title"] = title
        episode["episode_title"] = title
        episodes.append(episode)
    return sorted(episodes, key=lambda value: value["position"])


def _normalize_media(values: Any) -> list[dict[str, Any]]:
    media: list[dict[str, Any]] = []
    seen_positions: set[int] = set()
    if not isinstance(values, list):
        return media
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            continue
        entry = dict(value)
        position = _integer(entry.get("position"))
        position = index if position is None else position
        if position < 0 or position in seen_positions:
            raise ValueError("Media positions must be unique non-negative integers")
        seen_positions.add(position)
        entry["id"] = _component_id(entry.get("id"), "media")
        entry["position"] = position
        number = _integer(entry.get("media_number", entry.get("disc_number", entry.get("medium_number"))))
        if number is not None:
            entry["media_number"] = number
        media.append(entry)
    return sorted(media, key=lambda value: value["position"])


def _normalize_identifiers(values: Any, label: str) -> list[dict[str, Any]]:
    identifiers: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    if not isinstance(values, list):
        return identifiers
    for value in values:
        if isinstance(value, str):
            identifier = {"identifier_type": "other", "value": value.strip()}
        elif isinstance(value, Mapping):
            identifier = dict(value)
        else:
            continue
        identifier_type = _optional_string(identifier.get("identifier_type")) or "other"
        raw_value = _optional_string(identifier.get("value"))
        if raw_value is None:
            continue
        normalized = _optional_string(identifier.get("normalized_value")) or _normalize(raw_value)
        identity = identifier_type, normalized
        if identity in seen:
            raise ValueError(f"{label} identifiers must be unique by type and normalized value")
        seen.add(identity)
        identifiers.append(
            {
                **identifier,
                "id": _component_id(identifier.get("id"), f"{label} identifier"),
                "identifier_type": identifier_type,
                "value": raw_value,
                "normalized_value": normalized,
                "is_primary": identifier.get("is_primary") is True,
            }
        )
    return identifiers


def _component_id(value: Any, label: str) -> str:
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(str(value)))
    except ValueError as error:
        raise ValueError(f"{label} id must be a UUID") from error


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
