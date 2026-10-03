from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EntityPerson,
    EntityTag,
    Person,
    StoryArc,
    StoryArcItem,
    Tag,
)
from app.models.base import ItemKind
from app.models.catalog_anime_item import AnimeItem
from app.models.catalog_boardgame_item import BoardGameItem
from app.models.catalog_book_item import BookItem
from app.models.catalog_book_series import BookSeries
from app.models.catalog_comic_item import ComicItem
from app.models.catalog_game_item import GameItem
from app.models.catalog_manga_item import MangaItem
from app.models.catalog_movie_item import MovieItem
from app.models.catalog_music_item import MusicItem
from app.models.catalog_tv_item import TvItem
from app.scripts.seed_cover_lookup import resolve_seed_cover_urls

SEED_MARKER = "seed-native"


@dataclass(frozen=True)
class _Entry:
    kind: ItemKind
    title: str
    series_title: str
    publisher: str
    release_date: date
    creator: tuple[str, str]
    character: str | None = None
    tag: str | None = None
    story_arc: str | None = None


_ENTRIES: dict[ItemKind, list[_Entry]] = {
    ItemKind.book: [
        _Entry(ItemKind.book, "Dune", "Dune", "Ace Books", date(1965, 8, 1), ("Frank Herbert", "author"), "Paul Atreides", "sci-fi", "Arrakis"),
        _Entry(ItemKind.book, "Dune Messiah", "Dune", "Ace Books", date(1969, 10, 1), ("Frank Herbert", "author"), "Paul Atreides", "sci-fi", "Arrakis"),
    ],
    ItemKind.comic: [
        _Entry(ItemKind.comic, "The Amazing Spider-Man", "The Amazing Spider-Man", "Marvel", date(1963, 3, 1), ("Stan Lee", "writer"), "Spider-Man", "superhero", "Clone Saga"),
        _Entry(ItemKind.comic, "Batman", "Batman", "DC Comics", date(2016, 6, 15), ("Scott Snyder", "writer"), "Batman", "superhero", "Gotham"),
    ],
    ItemKind.manga: [
        _Entry(ItemKind.manga, "Chainsaw Man", "Chainsaw Man", "Shueisha", date(2018, 12, 3), ("Tatsuki Fujimoto", "mangaka"), "Denji", "shonen"),
        _Entry(ItemKind.manga, "Attack on Titan", "Attack on Titan", "Kodansha", date(2009, 9, 9), ("Hajime Isayama", "mangaka"), "Eren Yeager", "dark fantasy"),
    ],
    ItemKind.anime: [
        _Entry(ItemKind.anime, "Cowboy Bebop", "Cowboy Bebop", "Sunrise", date(1998, 4, 3), ("Shinichiro Watanabe", "director"), "Spike Spiegel", "sci-fi"),
        _Entry(ItemKind.anime, "Fullmetal Alchemist: Brotherhood", "Fullmetal Alchemist: Brotherhood", "Bones", date(2009, 4, 5), ("Hiromu Arakawa", "creator"), "Edward Elric", "adventure"),
    ],
    ItemKind.movie: [
        _Entry(ItemKind.movie, "Batman Begins", "The Dark Knight Trilogy", "Warner Bros.", date(2005, 6, 15), ("Christopher Nolan", "director"), "Bruce Wayne", "superhero"),
        _Entry(ItemKind.movie, "Blade Runner 2049", "Blade Runner", "Warner Bros.", date(2017, 10, 6), ("Denis Villeneuve", "director"), "Officer K", "sci-fi"),
    ],
    ItemKind.tv: [
        _Entry(ItemKind.tv, "Breaking Bad", "Breaking Bad", "AMC", date(2008, 1, 20), ("Vince Gilligan", "creator"), "Walter White", "crime"),
        _Entry(ItemKind.tv, "Chernobyl", "Chernobyl", "HBO", date(2019, 5, 6), ("Craig Mazin", "creator"), "Valery Legasov", "historical"),
    ],
    ItemKind.music: [
        _Entry(ItemKind.music, "The Dark Side of the Moon", "Pink Floyd Discography", "Harvest Records", date(1973, 3, 1), ("Roger Waters", "musician"), None, "rock"),
        _Entry(ItemKind.music, "OK Computer", "Radiohead Discography", "Parlophone", date(1997, 5, 21), ("Thom Yorke", "musician"), None, "rock"),
    ],
    ItemKind.game: [
        _Entry(ItemKind.game, "The Elder Scrolls V: Skyrim", "The Elder Scrolls", "Bethesda", date(2011, 11, 11), ("Todd Howard", "director"), None, "rpg"),
        _Entry(ItemKind.game, "Dark Souls", "Dark Souls", "FromSoftware", date(2011, 9, 22), ("Hidetaka Miyazaki", "director"), None, "action"),
    ],
    ItemKind.boardgame: [
        _Entry(ItemKind.boardgame, "Catan", "Catan", "Kosmos", date(1995, 1, 1), ("Klaus Teuber", "designer"), None, "strategy"),
        _Entry(ItemKind.boardgame, "Pandemic", "Pandemic", "Z-Man Games", date(2008, 1, 1), ("Matt Leacock", "designer"), None, "cooperative"),
    ],
}


def _slug(value: str) -> str:
    return value.lower().replace(":", "").replace("'", "").replace(" ", "-")


def _seed_age_rating(kind: ItemKind) -> str | None:
    if kind == ItemKind.movie:
        return "PG-13"
    if kind == ItemKind.tv:
        return "TV-MA"
    if kind == ItemKind.anime:
        return "TV-14"
    if kind == ItemKind.game:
        return "Teen"
    if kind == ItemKind.boardgame:
        return "10+"
    return "PG"


def _seed_runtime_minutes(kind: ItemKind) -> int | None:
    if kind == ItemKind.movie:
        return 120
    if kind == ItemKind.tv:
        return 42
    if kind == ItemKind.anime:
        return 24
    return None


def _seed_media_count(kind: ItemKind) -> int | None:
    if kind in {ItemKind.movie, ItemKind.tv, ItemKind.music}:
        return 1
    return None


def _apply_seed_metadata(
    target: Any,
    entry: _Entry,
    kind: ItemKind,
    index: int,
    cover_url: str | None,
    thumbnail_url: str | None,
) -> None:
    values = {
        "original_title": entry.title,
        "original_language": "en",
        "original_publication_date": entry.release_date,
        "original_publisher": entry.publisher,
        "original_release_date": entry.release_date,
        "original_air_date": entry.release_date,
        "first_air_date": entry.release_date,
        "last_air_date": entry.release_date,
        "release_status": "released",
        "status": "completed",
        "content_rating": _seed_age_rating(kind),
        "age_rating": _seed_age_rating(kind),
        "audience_rating": 4.5 if kind == ItemKind.music else _seed_age_rating(kind),
        "cover_image_url": cover_url,
        "poster_url": cover_url,
        "backdrop_url": thumbnail_url,
        "runtime_minutes": _seed_runtime_minutes(kind),
        "media_count": _seed_media_count(kind),
        "episode_count": 1 if kind in {ItemKind.tv, ItemKind.anime} else None,
        "season_count": 1 if kind == ItemKind.tv else None,
        "track_count": 1 if kind == ItemKind.music else None,
        "catalog_number": f"SEED-{kind.value.upper()}-{index:03d}",
        "barcode": f"SEED-{kind.value.upper()}-{index:03d}",
        "platform": "PC" if kind == ItemKind.game else None,
        "media_type": "disc" if kind in {ItemKind.movie, ItemKind.tv} else None,
        "format": "Blu-ray" if kind == ItemKind.movie else None,
        "packaging": "digipak" if kind == ItemKind.music else None,
        "sound_type": "stereo" if kind == ItemKind.music else None,
        "vinyl_color": "black" if kind == ItemKind.music else None,
        "vinyl_weight": "180g" if kind == ItemKind.music else None,
        "rpm": 33 if kind == ItemKind.music else None,
    }

    for attr, value in values.items():
        if value is not None and hasattr(target, attr):
            setattr(target, attr, value)


async def seed_catalog(db: AsyncSession, *, entries_per_kind: int) -> list[Any]:
    created: list[Any] = []
    for kind, entries in _ENTRIES.items():
        for index, entry in enumerate(entries[:entries_per_kind], start=1):
            created.extend(await _seed_entry(db, kind, entry, index))
    await db.commit()
    return created


async def _seed_entry(db: AsyncSession, kind: ItemKind, entry: _Entry, index: int) -> list[Any]:
    cover_url, thumbnail_url = await resolve_seed_cover_urls(
        kind=kind,
        slug=_slug(entry.series_title),
        title=entry.title,
        series=entry.series_title,
        fallback_key=f"{SEED_MARKER}-{kind.value}-{index}-{_slug(entry.title)}",
    )
    created: list[Any] = []
    if kind == ItemKind.book:
        created.extend(await _seed_book(db, entry, cover_url, thumbnail_url, index))
    elif kind == ItemKind.comic:
        created.extend(await _seed_comic(db, entry, cover_url, thumbnail_url, index))
    elif kind == ItemKind.manga:
        created.extend(await _seed_manga(db, entry, cover_url, thumbnail_url, index))
    elif kind == ItemKind.anime:
        created.extend(await _seed_anime(db, entry, cover_url, thumbnail_url, index))
    elif kind == ItemKind.movie:
        created.extend(await _seed_movie(db, entry, cover_url, thumbnail_url, index))
    elif kind == ItemKind.tv:
        created.extend(await _seed_tv(db, entry, cover_url, thumbnail_url, index))
    elif kind == ItemKind.music:
        created.extend(await _seed_music(db, entry, cover_url, thumbnail_url, index))
    elif kind == ItemKind.game:
        created.extend(await _seed_game(db, entry, cover_url, thumbnail_url, index))
    elif kind == ItemKind.boardgame:
        created.extend(await _seed_boardgame(db, entry, cover_url, thumbnail_url, index))
    return created


async def _seed_book(db: AsyncSession, entry: _Entry, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    item = (
        await db.execute(select(BookItem).where(BookItem.title == entry.title))
    ).scalar_one_or_none()
    if item is None:
        item = BookItem(
            title=entry.title,
            sort_key=_slug(entry.title),
            barcode=f"SEED-BOOK-{index:03d}",
            catalog_number=f"SEED-BOOK-{index:03d}",
            details={},
        )
        db.add(item)
        await db.flush()

    item.details = {
        **(item.details or {}),
        "original_title": entry.title,
        "release_date": entry.release_date.isoformat(),
        "publisher": entry.publisher,
        "series_title": entry.series_title,
        "language": "en",
        "country": "US",
        "physical_format": "Paperback",
        "age_rating": "General",
        "description": f"Seed data for {entry.title}.",
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
    }
    series = await _get_or_create_series(
        db,
        BookSeries,
        entry.series_title,
        entry.publisher,
        entry.release_date,
    )
    if series is not None:
        await _ensure_book_item_series_membership(db, item, series.id, index)
    if not item.details.get("printings"):
        item.details["printings"] = [{
            "id": str(uuid4()),
            "printing_number": 1,
            "title": entry.title,
            "release_date": entry.release_date.isoformat(),
            "publisher": entry.publisher,
            "language": "en",
        }]
    if not item.details.get("credits"):
        item.details["credits"] = [{
            "id": str(uuid4()),
            "credit_type": "creator",
            "name": entry.creator[0],
            "role": entry.creator[1],
            "sequence": 1,
        }]
    item.details = dict(item.details)
    await _ensure_person_link(db, item.id, "catalog_book_item", entry.creator, "creator")
    await _ensure_tag_link(db, item.id, "catalog_book_item", entry.tag)
    await _ensure_story_arc_link(db, item.id, "catalog_book_item", entry.story_arc)
    return [item]


async def _seed_comic(db: AsyncSession, entry: _Entry, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    title = f"{entry.title} #1"
    item = (
        await db.execute(select(ComicItem).where(ComicItem.title == title))
    ).scalar_one_or_none()
    if item is None:
        item = ComicItem(title=title, sort_key=_slug(title), details={})
        db.add(item)
        await db.flush()
    item.sort_key = _slug(title)
    item.barcode = f"SEED-COMIC-{index:03d}"
    item.catalog_number = f"SEED-COMIC-{index:03d}"
    item.details = {
        **dict(item.details or {}),
        "original_title": entry.title,
        "series_title": entry.series_title,
        "issue_number": "1",
        "release_date": entry.release_date.isoformat(),
        "release_date_parts": {
            "year": entry.release_date.year,
            "month": entry.release_date.month,
            "day": entry.release_date.day,
        },
        "publisher": entry.publisher,
        "country": "US",
        "language": "en",
        "age_rating": "PG",
        "genres": [entry.tag] if entry.tag else [],
        "creators": [{"name": entry.creator[0], "role": entry.creator[1]}],
        "characters": [entry.character] if entry.character else [],
        "story_arcs": [entry.story_arc] if entry.story_arc else [],
        "description": f"Seed data for {entry.title}.",
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
    }
    await _ensure_person_link(db, item.id, "catalog_comic_item", entry.creator, "creator")
    await _ensure_tag_link(db, item.id, "catalog_comic_item", entry.tag)
    await _ensure_story_arc_link(db, item.id, "catalog_comic_item", entry.story_arc)
    await _ensure_character_appearance(
        db,
        item.id,
        entry.character,
        entity_type="catalog_comic_item",
    )
    return [item]


async def _seed_manga(db: AsyncSession, entry: _Entry, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    title = f"{entry.title} Vol. {index}"
    item = (
        await db.execute(select(MangaItem).where(MangaItem.title == title))
    ).scalar_one_or_none()
    if item is None:
        item = MangaItem(title=title, sort_key=_slug(title), details={})
        db.add(item)
        await db.flush()
    item.sort_key = _slug(title)
    item.barcode = f"SEED-MANGA-{index:03d}"
    item.catalog_number = f"SEED-MANGA-{index:03d}"
    item.details = {
        **dict(item.details or {}),
        "series_title": entry.series_title,
        "volume_number": str(index),
        "item_number": str(index),
        "release_date": entry.release_date.isoformat(),
        "release_date_parts": {
            "year": entry.release_date.year,
            "month": entry.release_date.month,
            "day": entry.release_date.day,
        },
        "publisher": entry.publisher,
        "country": "JP",
        "language": "ja",
        "genres": [entry.tag] if entry.tag else [],
        "creators": [{"name": entry.creator[0], "role": entry.creator[1]}],
        "characters": [entry.character] if entry.character else [],
        "chapters": [
            {
                "chapter_number": 1,
                "title": entry.title,
                "release_date": entry.release_date.isoformat(),
                "description": entry.series_title,
                "cover_image_url": cover_url,
            }
        ],
        "description": f"Seed data for {entry.title}.",
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
    }
    await _ensure_person_link(db, item.id, "catalog_manga_item", entry.creator, "creator")
    await _ensure_tag_link(db, item.id, "catalog_manga_item", entry.tag)
    await _ensure_story_arc_link(db, item.id, "catalog_manga_item", entry.story_arc)
    await _ensure_character_appearance(
        db,
        item.id,
        entry.character,
        entity_type="catalog_manga_item",
    )
    return [item]


async def _seed_anime(db: AsyncSession, entry: _Entry, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    item = (
        await db.execute(select(AnimeItem).where(AnimeItem.title == entry.title))
    ).scalar_one_or_none()
    if item is None:
        item = AnimeItem(title=entry.title, sort_key=_slug(entry.title), details={})
        db.add(item)
        await db.flush()
    item.sort_key = _slug(entry.title)
    item.barcode = f"SEED-ANIME-{index:03d}"
    item.catalog_number = f"SEED-ANIME-{index:03d}"
    item.details = {
        **dict(item.details or {}),
        "series_title": entry.series_title,
        "item_number": str(index),
        "release_date": entry.release_date.isoformat(),
        "release_date_parts": {
            "year": entry.release_date.year,
            "month": entry.release_date.month,
            "day": entry.release_date.day,
        },
        "publisher": entry.publisher,
        "country": "JP",
        "language": "ja",
        "genres": [entry.tag] if entry.tag else [],
        "creators": [{"name": entry.creator[0], "role": entry.creator[1]}],
        "characters": [entry.character] if entry.character else [],
        "release_status": "completed",
        "description": f"Seed data for {entry.title}.",
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
    }
    if not item.details.get("media"):
        item.details["media"] = [{"id": str(uuid4()), "position": 0, "media_number": 1}]
    if not item.details.get("episodes"):
        item.details["episodes"] = [{
            "id": str(uuid4()),
            "position": 0,
            "episode_number": index,
            "title": entry.title,
            "episode_title": entry.title,
            "air_date": entry.release_date.isoformat(),
            "description": entry.series_title,
            "runtime_minutes": 24,
            "cover_image_url": cover_url,
        }]
    item.details = dict(item.details)
    await _ensure_person_link(db, item.id, "catalog_anime_item", entry.creator, "creator")
    await _ensure_tag_link(db, item.id, "catalog_anime_item", entry.tag)
    await _ensure_story_arc_link(db, item.id, "catalog_anime_item", entry.story_arc)
    await _ensure_character_appearance(
        db,
        item.id,
        entry.character,
        entity_type="catalog_anime_item",
    )
    return [item]


async def _seed_movie(db: AsyncSession, entry: _Entry, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    item = (
        await db.execute(select(MovieItem).where(MovieItem.title == entry.title))
    ).scalar_one_or_none()
    if item is None:
        item = MovieItem(
            title=entry.title,
            sort_key=_slug(entry.title),
            barcode=f"MOV-{index:03d}",
            catalog_number=f"SEED-MOVIE-{index:03d}",
            details={},
        )
        db.add(item)
        await db.flush()
    item.details = {
        **dict(item.details or {}),
        "original_title": entry.title,
        "release_date": entry.release_date.isoformat(),
        "release_date_parts": {
            "year": entry.release_date.year,
            "month": entry.release_date.month,
            "day": entry.release_date.day,
        },
        "publisher": entry.publisher,
        "country": "US",
        "physical_format": "Blu-ray",
        "runtime_minutes": _seed_runtime_minutes(ItemKind.movie),
        "age_rating": _seed_age_rating(ItemKind.movie),
        "genres": [entry.tag] if entry.tag else [],
        "creators": [{"name": entry.creator[0], "role": entry.creator[1]}],
        "characters": [entry.character] if entry.character else [],
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
    }
    await _ensure_person_link(db, item.id, "catalog_movie_item", entry.creator, "director")
    media = item.details.get("media") or []
    if not media:
        item.details["media"] = [{
            "id": str(uuid4()),
            "media_number": 1,
            "media_type": "disc",
            "title": entry.title,
            "color": "color",
        }]
        item.details = dict(item.details)
    return [item]


async def _seed_tv(db: AsyncSession, entry: _Entry, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    barcode = f"SEED-TV-{index:03d}"
    item = (
        await db.execute(select(TvItem).where(TvItem.barcode == barcode))
    ).scalar_one_or_none()
    if item is None:
        item = TvItem(title=entry.title, barcode=barcode)
        db.add(item)
    item.title = entry.title
    item.sort_key = _slug(entry.title)
    item.catalog_number = f"SEED-TV-{index:03d}"
    item.details = {
        "original_title": entry.title,
        "original_language": "en",
        "release_date": entry.release_date.isoformat(),
        "original_release_date": entry.release_date.isoformat(),
        "publisher": entry.publisher,
        "country": "US",
        "physical_format": "Blu-ray",
        "runtime_minutes": 42,
        "age_rating": _seed_age_rating(ItemKind.tv),
        "genres": [entry.tag] if entry.tag else [],
        "creators": [{"name": entry.creator[0], "role": entry.creator[1]}],
        "characters": [entry.character] if entry.character else [],
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
    }
    await db.flush()
    await _ensure_person_link(db, item.id, "catalog_tv_item", entry.creator, "creator")
    if not item.details.get("media"):
        item.details["media"] = [{
            "id": str(uuid4()),
            "position": 0,
            "media_number": 1,
            "media_type": "season",
            "title": entry.title,
            "episode_count": 1,
            "runtime_minutes": 42,
            "region_code": "US",
            "encoding": "digital",
        }]
    if not item.details.get("episodes"):
        item.details["episodes"] = [{
            "id": str(uuid4()),
            "position": 0,
            "season_number": 1,
            "episode_number": index,
            "title": entry.title,
            "episode_title": entry.title,
            "overview": entry.series_title,
            "original_air_date": entry.release_date.isoformat(),
            "runtime_minutes": 42,
        }]
    if not item.details.get("seasons"):
        item.details["seasons"] = [{
            "id": str(uuid4()),
            "season_number": 1,
            "title": entry.series_title,
            "episode_count": 1,
            "release_date": entry.release_date.isoformat(),
            "description": f"Seed season for {entry.series_title}.",
        }]
    item.details = dict(item.details)
    await db.flush()
    return [item]


async def _seed_music(
    db: AsyncSession,
    entry: _Entry,
    cover_url: str | None,
    thumbnail_url: str | None,
    index: int,
) -> list[Any]:
    barcode = f"SEED-MUSIC-{index:03d}"
    item = (
        await db.execute(select(MusicItem).where(MusicItem.barcode == barcode))
    ).scalar_one_or_none()
    if item is None:
        item = MusicItem(title=entry.title, barcode=barcode)
        db.add(item)
    item.sort_title = _slug(entry.title)
    item.artist = entry.creator[0]
    item.artist_credits = [{"name": entry.creator[0]}]
    item.release_date = entry.release_date
    item.release_date_parts = {
        "year": entry.release_date.year,
        "month": entry.release_date.month,
        "day": entry.release_date.day,
    }
    item.label = entry.publisher
    item.format = "CD"
    item.catalog_number = f"SEED-MUSIC-CAT-{index:03d}"
    item.genres = [entry.tag] if entry.tag else []
    item.packaging = "digipak"
    item.sound_types = ["stereo"]
    item.cover_image_url = cover_url
    item.thumbnail_image_url = thumbnail_url
    await db.flush()

    existing = item.discs[0] if item.discs else {}
    existing_track = (existing.get("tracks") or [{}])[0]
    item.discs = [{
        **existing, "disc_number": 1, "title": "Disc 1",
        "tracks": [{
            **existing_track, "position": "1", "position_order": 0,
            "title": f"{entry.title} Track 1", "artist": entry.creator[0],
            "duration_ms": 180000,
        }],
    }]
    await db.flush()
    return [item]


async def _seed_game(
    db: AsyncSession,
    entry: _Entry,
    cover_url: str | None,
    thumbnail_url: str | None,
    index: int,
) -> list[Any]:
    item = (
        await db.execute(select(GameItem).where(GameItem.title == entry.title))
    ).scalar_one_or_none()
    if item is None:
        item = GameItem(
            title=entry.title,
            sort_key=_slug(entry.title),
            barcode=f"GAME-{index:03d}",
            catalog_number=f"SEED-GAME-{index:03d}",
            details={},
        )
        db.add(item)
        await db.flush()
    item.details = {
        **dict(item.details or {}),
        "original_title": entry.title,
        "release_date": entry.release_date.isoformat(),
        "release_date_parts": {
            "year": entry.release_date.year,
            "month": entry.release_date.month,
            "day": entry.release_date.day,
        },
        "release_region": "US",
        "publisher": entry.publisher,
        "physical_format": "digital",
        "language": "en",
        "age_rating": _seed_age_rating(ItemKind.game),
        "genres": [entry.tag] if entry.tag else [],
        "platforms": ["PC"],
        "company_roles": ["developer"],
        "creators": [{"name": entry.creator[0], "role": entry.creator[1]}],
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
    }
    return [item]


async def _seed_boardgame(
    db: AsyncSession,
    entry: _Entry,
    cover_url: str | None,
    thumbnail_url: str | None,
    index: int,
) -> list[Any]:
    item = (
        await db.execute(select(BoardGameItem).where(BoardGameItem.title == entry.title))
    ).scalar_one_or_none()
    if item is None:
        item = BoardGameItem(
            title=entry.title,
            sort_key=_slug(entry.title),
            barcode=f"BOARDGAME-{index:03d}",
            catalog_number=f"SEED-BOARDGAME-{index:03d}",
            details={},
        )
        db.add(item)
        await db.flush()
    item.details = {
        **dict(item.details or {}),
        "original_title": entry.title,
        "year_published": entry.release_date.year,
        "release_date": entry.release_date.isoformat(),
        "release_date_parts": {
            "year": entry.release_date.year,
            "month": entry.release_date.month,
            "day": entry.release_date.day,
        },
        "country": "US",
        "publisher": entry.publisher,
        "physical_format": "standard",
        "age_rating": _seed_age_rating(ItemKind.boardgame),
        "min_players": 2,
        "max_players": 4,
        "playing_time_minutes": 60,
        "min_age": 10,
        "genres": [entry.tag] if entry.tag else [],
        "platforms": [],
        "contributors": [{"name": entry.creator[0], "role": entry.creator[1]}],
        "cover_image_url": cover_url,
        "thumbnail_image_url": thumbnail_url,
    }
    return [item]


async def _get_or_create_series(db: AsyncSession, model: type, title: str, publisher: str, release_date: date):
    result = await db.execute(select(model).where(model.title == title))
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    kwargs = {"title": title, "description": f"Seed data for {title}."}
    if hasattr(model, "slug"):
        kwargs["slug"] = _slug(title)
    if hasattr(model, "sort_title"):
        kwargs["sort_title"] = _slug(title)
    if hasattr(model, "original_title"):
        kwargs["original_title"] = title
    if hasattr(model, "start_date"):
        kwargs["start_date"] = release_date
    if hasattr(model, "original_publication_date"):
        kwargs["original_publication_date"] = release_date
    if hasattr(model, "original_air_date"):
        kwargs["original_air_date"] = release_date
    if hasattr(model, "status"):
        kwargs["status"] = "completed"
    if hasattr(model, "language"):
        kwargs["language"] = "en"
    if hasattr(model, "country"):
        kwargs["country"] = "US"
    if hasattr(model, "original_language"):
        kwargs["original_language"] = "en"
    if hasattr(model, "anime_type"):
        kwargs["anime_type"] = "tv"
    if hasattr(model, "episode_count"):
        kwargs["episode_count"] = 12
    row = model(**kwargs)
    db.add(row)
    await db.flush()
    return row


async def _ensure_person_link(db: AsyncSession, entity_id: Any, entity_type: str, creator: tuple[str, str], role: str) -> None:
    name, creator_role = creator
    result = await db.execute(select(Person).where(Person.name == name))
    person = result.scalar_one_or_none()
    if person is None:
        person = Person(name=name)
        db.add(person)
        await db.flush()
    result = await db.execute(
        select(EntityPerson).where(
            EntityPerson.entity_type == entity_type,
            EntityPerson.entity_id == entity_id,
            EntityPerson.person_id == person.id,
            EntityPerson.role == role,
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(EntityPerson(entity_type=entity_type, entity_id=entity_id, person_id=person.id, role=role))


async def _ensure_tag_link(db: AsyncSession, entity_id: Any, entity_type: str, tag_name: str | None) -> None:
    if not tag_name:
        return
    tag_kind = {
        "catalog_anime_item": "anime",
        "catalog_book_item": "book",
        "catalog_comic_item": "comic",
        "catalog_manga_item": "manga",
    }.get(entity_type, entity_type.replace("_work", ""))
    result = await db.execute(select(Tag).where(Tag.kind == tag_kind, Tag.name == tag_name))
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = Tag(kind=tag_kind, name=tag_name)
        db.add(tag)
        await db.flush()
    result = await db.execute(
        select(EntityTag).where(EntityTag.entity_type == entity_type, EntityTag.entity_id == entity_id, EntityTag.tag_id == tag.id)
    )
    if result.scalar_one_or_none() is None:
        db.add(EntityTag(entity_type=entity_type, entity_id=entity_id, tag_id=tag.id))


async def _ensure_story_arc_link(db: AsyncSession, entity_id: Any, entity_type: str, arc_name: str | None) -> None:
    if not arc_name:
        return
    result = await db.execute(select(StoryArc).where(StoryArc.name == arc_name))
    arc = result.scalar_one_or_none()
    if arc is None:
        arc = StoryArc(name=arc_name, description=f"Seed arc {arc_name}", publisher=None)
        db.add(arc)
        await db.flush()
    result = await db.execute(
        select(StoryArcItem).where(
            StoryArcItem.story_arc_id == arc.id,
            StoryArcItem.entity_type == entity_type,
            StoryArcItem.entity_id == entity_id,
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(StoryArcItem(story_arc_id=arc.id, entity_type=entity_type, entity_id=entity_id, ordinal=1))


async def _ensure_book_item_series_membership(
    db: AsyncSession,
    item: BookItem,
    series_id: Any,
    index: int,
) -> None:
    memberships = list(item.details.get("series_memberships") or [])
    if not any(str(value.get("series_id")) == str(series_id) for value in memberships):
        memberships.append({
            "series_id": str(series_id),
            "sequence": float(index),
            "display_number": str(index),
        })
        item.details = {**item.details, "series_memberships": memberships}


async def _ensure_character_appearance(
    db: AsyncSession,
    entity_id: Any,
    character_name: str | None,
    *,
    entity_type: str,
) -> None:
    if not character_name:
        return
    from app.models import (  # local import to avoid circulars in all files
        Character,
        CharacterAppearance,
    )

    result = await db.execute(select(Character).where(Character.name == character_name))
    character = result.scalar_one_or_none()
    if character is None:
        character = Character(name=character_name, description=f"Seed character {character_name}")
        db.add(character)
        await db.flush()
    result = await db.execute(
        select(CharacterAppearance).where(
            CharacterAppearance.entity_type == entity_type,
            CharacterAppearance.entity_id == entity_id,
            CharacterAppearance.character_id == character.id,
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(
            CharacterAppearance(
                entity_type=entity_type,
                entity_id=entity_id,
                character_id=character.id,
                role="main",
            )
        )
