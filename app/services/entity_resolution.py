from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnimeEpisode,
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookEdition,
    BookWork,
    BundleRelease,
    Character,
    ComicIssue,
    ComicSeries,
    ComicVolume,
    ComicWork,
    GameRelease,
    GameWork,
    MangaChapter,
    MangaSeries,
    MangaWork,
    MovieWork,
    MusicRelease,
    Organization,
    Person,
    StoryArc,
    Tag,
    TVRelease,
)
from app.models.base import ItemKind
from app.models.entity_refs import DEFAULT_ENTITY_REF_REGISTRY


@dataclass(frozen=True)
class EntitySummary:
    entity_type: str
    entity_id: UUID
    kind: ItemKind | None
    title: str
    item_number: str | None
    series_title: str | None
    volume_name: str | None
    cover_image_url: str | None
    metadata_json: dict[str, Any] | None


ENTITY_MODEL_BY_TYPE: dict[str, type[Any]] = {
    "anime_episode": AnimeEpisode,
    "anime_series": AnimeSeries,
    "boardgame_edition": BoardGameEdition,
    "boardgame_work": BoardGameWork,
    "book_edition": BookEdition,
    "book_work": BookWork,
    "bundle_release": BundleRelease,
    "character": Character,
    "comic_issue": ComicIssue,
    "comic_series": ComicSeries,
    "comic_volume": ComicVolume,
    "comic_work": ComicWork,
    "game_release": GameRelease,
    "game_work": GameWork,
    "manga_chapter": MangaChapter,
    "manga_series": MangaSeries,
    "manga_work": MangaWork,
    "movie_work": MovieWork,
    "music_release": MusicRelease,
    "organization": Organization,
    "person": Person,
    "story_arc": StoryArc,
    "tag": Tag,
    "tv_release": TVRelease,
}

_TITLE_FIELDS = ("title", "display_title", "chapter_title", "episode_title", "name", "series_title")
_NUMBER_FIELDS = ("item_number", "issue_number", "chapter_number", "episode_number", "season_number", "release_number", "volume_number", "media_number")
_COVER_FIELDS = ("cover_image_url", "thumbnail_image_url", "image_url")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metadata_text(metadata: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    return _text(metadata.get(key))


def _first_text(entity: object, fields: tuple[str, ...]) -> str | None:
    for field in fields:
        value = _text(getattr(entity, field, None))
        if value:
            return value
    return None


def _entity_kind(entity_type: str) -> ItemKind | None:
    spec = DEFAULT_ENTITY_REF_REGISTRY.spec_for(entity_type)
    return spec.kind if spec is not None else None


def entity_summary(entity_type: str, entity_id: UUID, entity: object) -> EntitySummary:
    metadata = getattr(entity, "metadata_json", None)
    title = _first_text(entity, _TITLE_FIELDS) or entity_type
    item_number = _first_text(entity, _NUMBER_FIELDS)
    series_title = _metadata_text(metadata, "series_title")
    volume_name = _metadata_text(metadata, "volume_name")
    cover_image_url = _first_text(entity, _COVER_FIELDS) or _metadata_text(metadata, "cover_image_url")
    return EntitySummary(
        entity_type=entity_type,
        entity_id=entity_id,
        kind=_entity_kind(entity_type),
        title=title,
        item_number=item_number,
        series_title=series_title,
        volume_name=volume_name,
        cover_image_url=cover_image_url,
        metadata_json=metadata if isinstance(metadata, dict) else None,
    )


async def load_entity_summaries(
    db: AsyncSession,
    refs: list[tuple[str, UUID]],
) -> dict[tuple[str, UUID], EntitySummary]:
    unique_refs = list(dict.fromkeys(refs))
    if not unique_refs:
        return {}

    refs_by_model: dict[type[Any], list[tuple[str, UUID]]] = {}
    for entity_type, entity_id in unique_refs:
        model_cls = ENTITY_MODEL_BY_TYPE.get(entity_type)
        if model_cls is None:
            continue
        refs_by_model.setdefault(model_cls, []).append((entity_type, entity_id))

    summaries: dict[tuple[str, UUID], EntitySummary] = {}
    for model_cls, model_refs in refs_by_model.items():
        ids = [entity_id for _, entity_id in model_refs]
        rows = (
            await db.execute(select(model_cls).where(model_cls.id.in_(ids)))
        ).scalars().all()
        rows_by_id = {row.id: row for row in rows}
        for entity_type, entity_id in model_refs:
            entity = rows_by_id.get(entity_id)
            if entity is None:
                continue
            summaries[(entity_type, entity_id)] = entity_summary(entity_type, entity_id, entity)
    return summaries
