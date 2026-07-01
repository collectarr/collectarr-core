from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AnimeCharacterAppearance,
    AnimeContribution,
    AnimeEpisode,
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookSeries,
    BookSeriesMembership,
    BookWork,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIssue,
    ComicSeries,
    ComicSeriesMembership,
    ComicStoryArcMembership,
    ComicVolume,
    ComicWork,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    GameRelease,
    GameWork,
    ImageAsset,
    MangaChapter,
    MangaContribution,
    MangaIdentifier,
    MangaSeries,
    MangaSeriesMembership,
    MangaWork,
    MovieRelease,
    MovieReleaseMedia,
    MovieWork,
    MovieWorkContribution,
    MovieWorkIdentifier,
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseIdentifier,
    MusicTrack,
    Organization,
    Person,
    StoryArc,
    StoryArcItem,
    Tag,
    TVEpisode,
    TVRelease,
    TVReleaseContribution,
    TVReleaseIdentifier,
    TVReleaseMedia,
)
from app.models.base import ExternalProvider, ItemKind
from app.scripts.seed_cover_lookup import resolve_seed_cover_urls
from app.search.client import SearchClient
from app.search.documents import catalog_search_document

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

_ENTITY_TYPE: dict[ItemKind, str] = {
    ItemKind.book: "book_work",
    ItemKind.comic: "comic_work",
    ItemKind.manga: "manga_work",
    ItemKind.anime: "anime_series",
    ItemKind.movie: "movie_work",
    ItemKind.tv: "tv_release",
    ItemKind.music: "music_release",
    ItemKind.game: "game_work",
    ItemKind.boardgame: "boardgame_work",
}


def _slug(value: str) -> str:
    return value.lower().replace(":", "").replace("'", "").replace(" ", "-")


async def seed_catalog(db: AsyncSession, *, entries_per_kind: int) -> list[Any]:
    created: list[Any] = []
    for kind, entries in _ENTRIES.items():
        for index, entry in enumerate(entries[:entries_per_kind], start=1):
            created.extend(await _seed_entry(db, kind, entry, index))
    await db.commit()
    return created


async def wipe_seed_data(db: AsyncSession) -> int:
    ids_by_type: dict[str, list[Any]] = {}
    for entity_type in _ENTITY_TYPE.values():
        result = await db.execute(
            select(ExternalProviderId.entity_id).where(
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.provider_item_id.startswith(SEED_MARKER),
            )
        )
        ids_by_type[entity_type] = [row[0] for row in result.all()]
    total = sum(len(ids) for ids in ids_by_type.values())
    if total == 0:
        return 0

    for entity_type, ids in ids_by_type.items():
        if not ids:
            continue
        await _delete_kind_rows(db, entity_type, ids)
        await db.execute(
            delete(ExternalProviderId).where(
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.provider_item_id.startswith(SEED_MARKER),
            )
        )
    await db.commit()
    return total


async def _seed_entry(db: AsyncSession, kind: ItemKind, entry: _Entry, index: int) -> list[Any]:
    provider = {
        ItemKind.book: ExternalProvider.openlibrary,
        ItemKind.comic: ExternalProvider.comicvine,
        ItemKind.manga: ExternalProvider.hardcover,
        ItemKind.anime: ExternalProvider.anilist,
        ItemKind.movie: ExternalProvider.tmdb,
        ItemKind.tv: ExternalProvider.tmdb,
        ItemKind.music: ExternalProvider.musicbrainz,
        ItemKind.game: ExternalProvider.igdb,
        ItemKind.boardgame: ExternalProvider.bgg,
    }[kind]
    cover_url, thumbnail_url = await resolve_seed_cover_urls(
        kind=kind,
        slug=_slug(entry.series_title),
        title=entry.title,
        series=entry.series_title,
        fallback_key=f"{SEED_MARKER}-{kind.value}-{index}-{_slug(entry.title)}",
    )
    created: list[Any] = []
    if kind == ItemKind.book:
        created.extend(await _seed_book(db, entry, provider, cover_url, thumbnail_url, index))
    elif kind == ItemKind.comic:
        created.extend(await _seed_comic(db, entry, provider, cover_url, thumbnail_url, index))
    elif kind == ItemKind.manga:
        created.extend(await _seed_manga(db, entry, provider, cover_url, thumbnail_url, index))
    elif kind == ItemKind.anime:
        created.extend(await _seed_anime(db, entry, provider, cover_url, thumbnail_url, index))
    elif kind == ItemKind.movie:
        created.extend(await _seed_movie(db, entry, provider, cover_url, thumbnail_url, index))
    elif kind == ItemKind.tv:
        created.extend(await _seed_tv(db, entry, provider, cover_url, thumbnail_url, index))
    elif kind == ItemKind.music:
        created.extend(await _seed_music(db, entry, provider, cover_url, thumbnail_url, index))
    elif kind == ItemKind.game:
        created.extend(await _seed_game(db, entry, provider, cover_url, thumbnail_url, index))
    elif kind == ItemKind.boardgame:
        created.extend(await _seed_boardgame(db, entry, provider, cover_url, thumbnail_url, index))
    return created


async def _seed_book(db: AsyncSession, entry: _Entry, provider: ExternalProvider, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    series = await _get_or_create_series(db, BookSeries, entry.series_title, entry.publisher, entry.release_date)
    work = await _get_or_create_work(db, BookWork, entry.title, entry.release_date, cover_url)
    if work not in []:
        work.original_publication_date = entry.release_date
    await _upsert_provider(db, _ENTITY_TYPE[ItemKind.book], work.id, provider, index, entry)
    await _ensure_person_link(db, work.id, "book_work", entry.creator, "creator")
    await _ensure_tag_link(db, work.id, "book_work", entry.tag)
    await _ensure_story_arc_link(db, work.id, "book_work", entry.story_arc)
    if series is not None:
        await _ensure_book_membership(db, work.id, series.id, index)
    edition = await _get_or_create_book_edition(db, work.id, entry, cover_url)
    await _ensure_book_links(db, edition.id, provider, index, entry)
    return [work]


async def _seed_comic(db: AsyncSession, entry: _Entry, provider: ExternalProvider, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    series = await _get_or_create_series(db, ComicSeries, entry.series_title, entry.publisher, entry.release_date)
    volume = await _get_or_create_volume(db, entry.series_title, entry.release_date)
    work = await _get_or_create_work(db, ComicWork, entry.title, entry.release_date, cover_url)
    work.volume = volume
    await _upsert_provider(db, _ENTITY_TYPE[ItemKind.comic], work.id, provider, index, entry)
    await _ensure_person_link(db, work.id, "comic_work", entry.creator, "creator")
    await _ensure_tag_link(db, work.id, "comic_work", entry.tag)
    await _ensure_story_arc_link(db, work.id, "comic_work", entry.story_arc)
    if series is not None:
        await _ensure_comic_membership(db, work.id, series.id, index)
    issue = await _get_or_create_comic_issue(db, work.id, entry, cover_url)
    await _ensure_character_appearance(db, issue.id, entry.character)
    await _ensure_story_arc_membership(db, issue.id, entry.story_arc)
    await _ensure_comic_links(db, issue.id, provider, index, entry)
    return [work]


async def _seed_manga(db: AsyncSession, entry: _Entry, provider: ExternalProvider, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    series = await _get_or_create_series(db, MangaSeries, entry.series_title, entry.publisher, entry.release_date)
    work = await _get_or_create_work(db, MangaWork, entry.title, entry.release_date, cover_url)
    await _upsert_provider(db, _ENTITY_TYPE[ItemKind.manga], work.id, provider, index, entry)
    await _ensure_person_link(db, work.id, "manga_work", entry.creator, "creator")
    await _ensure_tag_link(db, work.id, "manga_work", entry.tag)
    if series is not None:
        await _ensure_manga_membership(db, work.id, series.id, index)
    chapter = MangaChapter(work=work, chapter_number=float(index), chapter_title=entry.title, publication_date=entry.release_date, description=entry.series_title, cover_image_url=cover_url)
    db.add(chapter)
    await db.flush()
    await _ensure_manga_links(db, chapter.id, provider, index, entry)
    return [work]


async def _seed_anime(db: AsyncSession, entry: _Entry, provider: ExternalProvider, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    series = await _get_or_create_series(db, AnimeSeries, entry.series_title, entry.publisher, entry.release_date)
    if series is not None:
        series.original_air_date = entry.release_date
        series.status = "completed"
    await _upsert_provider(db, _ENTITY_TYPE[ItemKind.anime], series.id, provider, index, entry)
    await _ensure_person_link(db, series.id, "anime_series", entry.creator, "creator")
    await _ensure_tag_link(db, series.id, "anime_series", entry.tag)
    episode = AnimeEpisode(series=series, episode_number=index, episode_title=entry.title, air_date=entry.release_date, description=entry.series_title, cover_image_url=cover_url, runtime_minutes=24)
    db.add(episode)
    await db.flush()
    await _ensure_character_appearance(db, series.id, entry.character, entity_type="anime_series")
    await _ensure_anime_links(db, episode.id, provider, index, entry)
    return [series]


async def _seed_movie(db: AsyncSession, entry: _Entry, provider: ExternalProvider, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    work = await _get_or_create_work(db, MovieWork, entry.title, entry.release_date, cover_url)
    work.original_release_date = entry.release_date
    await _upsert_provider(db, _ENTITY_TYPE[ItemKind.movie], work.id, provider, index, entry)
    await _ensure_person_link(db, work.id, "movie_work", entry.creator, "director")
    release = MovieRelease(work=work, format="Blu-ray", region_code="US", release_date=entry.release_date, release_type="home_video", publisher=entry.publisher, barcode=f"MOV-{index:03d}", cover_image_url=cover_url)
    db.add(release)
    await db.flush()
    media = MovieReleaseMedia(release=release, media_number=1, media_type="disc", title=entry.title, color="color")
    db.add(media)
    await db.flush()
    return [work]


async def _seed_tv(db: AsyncSession, entry: _Entry, provider: ExternalProvider, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    release = await _get_or_create_tv_release(db, entry)
    await _upsert_provider(db, _ENTITY_TYPE[ItemKind.tv], release.id, provider, index, entry)
    await _ensure_person_link(db, release.id, "tv_release", entry.creator, "creator")
    media = TVReleaseMedia(release=release, media_number=1, media_type="season", title=entry.title, episode_count=1, runtime_minutes=42, region_code="US", encoding="digital")
    db.add(media)
    await db.flush()
    episode = TVEpisode(release=release, media=media, series_title=entry.series_title, season_number=1, episode_number=index, title=entry.title, original_air_date=entry.release_date)
    db.add(episode)
    await db.flush()
    await _ensure_tv_links(db, release.id, provider, index, entry)
    return [release]


async def _seed_music(db: AsyncSession, entry: _Entry, provider: ExternalProvider, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    release = await _get_or_create_music_release(db, entry, cover_url)
    await _upsert_provider(db, _ENTITY_TYPE[ItemKind.music], release.id, provider, index, entry)
    await _ensure_person_link(db, release.id, "music_release", entry.creator, "artist")
    media = MusicMedia(release=release, media_number=1, media_type="album", title=entry.title, packaging="digipak")
    db.add(media)
    await db.flush()
    db.add(MusicTrack(media=media, release=release, position="1", title=f"{entry.title} Track 1", duration_ms=180000))
    await db.flush()
    return [release]


async def _seed_game(db: AsyncSession, entry: _Entry, provider: ExternalProvider, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    work = await _get_or_create_work(db, GameWork, entry.title, entry.release_date, cover_url)
    work.original_language = "en"
    await _upsert_provider(db, _ENTITY_TYPE[ItemKind.game], work.id, provider, index, entry)
    await _ensure_person_link(db, work.id, "game_work", entry.creator, "designer")
    db.add(GameRelease(work=work, release_title=entry.title, platform="PC", release_date=entry.release_date, region_code="US", format="digital", publisher=entry.publisher, barcode=f"GAME-{index:03d}", cover_image_url=cover_url))
    await db.flush()
    return [work]


async def _seed_boardgame(db: AsyncSession, entry: _Entry, provider: ExternalProvider, cover_url: str | None, thumbnail_url: str | None, index: int) -> list[Any]:
    work = await _get_or_create_work(db, BoardGameWork, entry.title, entry.release_date, cover_url)
    await _upsert_provider(db, _ENTITY_TYPE[ItemKind.boardgame], work.id, provider, index, entry)
    await _ensure_person_link(db, work.id, "boardgame_work", entry.creator, "designer")
    db.add(BoardGameEdition(work=work, edition_title=entry.title, format="standard", publisher=entry.publisher, release_date=entry.release_date, country="US", cover_image_url=cover_url))
    await db.flush()
    return [work]


async def _get_or_create_series(db: AsyncSession, model: type, title: str, publisher: str, release_date: date):
    result = await db.execute(select(model).where(model.title == title))
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    kwargs = {
        "title": title,
        "slug": _slug(title),
        "description": f"Seed data for {title}.",
        "original_title": title,
        "start_date": release_date,
        "status": "completed",
        "language": "en",
        "country": "US",
        "metadata_json": {"seed": True, "publisher": publisher},
    }
    row = model(**kwargs)
    db.add(row)
    await db.flush()
    return row


async def _get_or_create_volume(db: AsyncSession, title: str, release_date: date) -> ComicVolume:
    result = await db.execute(select(ComicVolume).where(ComicVolume.title == title))
    volume = result.scalar_one_or_none()
    if volume is not None:
        return volume
    volume = ComicVolume(title=title, slug=_slug(title), start_year=release_date.year)
    db.add(volume)
    await db.flush()
    return volume


async def _get_or_create_work(db: AsyncSession, model: type, title: str, release_date: date, cover_url: str | None):
    result = await db.execute(select(model).where(model.title == title))
    work = result.scalar_one_or_none()
    if work is not None:
        if getattr(work, "cover_image_url", None) is None:
            work.cover_image_url = cover_url
        return work
    kwargs = {"title": title, "sort_title": _slug(title), "metadata_json": {"seed": True}}
    if hasattr(model, "description"):
        kwargs["description"] = f"Seed data for {title}."
    if hasattr(model, "cover_image_url"):
        kwargs["cover_image_url"] = cover_url
    if model is MovieWork:
        kwargs["original_release_date"] = release_date
    if model is BookWork:
        kwargs["original_publication_date"] = release_date
    work = model(**kwargs)
    db.add(work)
    await db.flush()
    return work


async def _get_or_create_book_edition(db: AsyncSession, work_id: Any, entry: _Entry, cover_url: str | None) -> BookEdition:
    result = await db.execute(select(BookEdition).where(BookEdition.work_id == work_id, BookEdition.display_title == entry.title))
    edition = result.scalar_one_or_none()
    if edition is not None:
        return edition
    edition = BookEdition(work_id=work_id, display_title=entry.title, format="Paperback", publication_date=entry.release_date, publisher=entry.publisher, language="en", region="US", cover_image_url=cover_url, metadata_json={"seed": True})
    db.add(edition)
    await db.flush()
    return edition


async def _get_or_create_comic_issue(db: AsyncSession, work_id: Any, entry: _Entry, cover_url: str | None) -> ComicIssue:
    result = await db.execute(select(ComicIssue).where(ComicIssue.work_id == work_id, ComicIssue.issue_number == "1"))
    issue = result.scalar_one_or_none()
    if issue is not None:
        return issue
    issue = ComicIssue(work_id=work_id, issue_number="1", display_title=entry.title, publication_date=entry.release_date, release_date=entry.release_date, publisher=entry.publisher, language="en", region="US", release_status="released", cover_image_url=cover_url, metadata_json={"seed": True})
    db.add(issue)
    await db.flush()
    return issue


async def _get_or_create_tv_release(db: AsyncSession, entry: _Entry) -> TVRelease:
    result = await db.execute(select(TVRelease).where(TVRelease.title == entry.title))
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    row = TVRelease(title=entry.title, sort_title=_slug(entry.title), description=f"Seed data for {entry.title}.", format="digital", release_date=entry.release_date, publisher=entry.publisher, content_rating="TV-MA", cover_image_url=None, metadata_json={"seed": True})
    db.add(row)
    await db.flush()
    return row


async def _get_or_create_music_release(db: AsyncSession, entry: _Entry, cover_url: str | None) -> MusicRelease:
    result = await db.execute(select(MusicRelease).where(MusicRelease.title == entry.title))
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    row = MusicRelease(title=entry.title, sort_title=_slug(entry.title), release_date=entry.release_date, release_type="album", release_status="released", media_count=1, track_count=1, cover_image_url=cover_url, publisher=entry.publisher, language="en", barcode=f"MUS-{_slug(entry.title)}", metadata_json={"seed": True})
    db.add(row)
    await db.flush()
    return row


async def _ensure_provider(db: AsyncSession, entity_type: str, entity_id: Any, provider: ExternalProvider, index: int, entry: _Entry) -> None:
    pid = f"{SEED_MARKER}-{entity_type}-{index}-{_slug(entry.title)}"
    result = await db.execute(
        select(ExternalProviderId).where(
            ExternalProviderId.entity_type == entity_type,
            ExternalProviderId.entity_id == entity_id,
            ExternalProviderId.provider == provider,
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(ExternalProviderId(provider=provider, provider_item_id=pid, entity_type=entity_type, entity_id=entity_id, site_url=f"https://example.com/{entity_type}/{pid}", api_url=f"https://api.example.com/{entity_type}/{pid}"))


async def _upsert_provider(db: AsyncSession, entity_type: str, entity_id: Any, provider: ExternalProvider, index: int, entry: _Entry) -> None:
    await _ensure_provider(db, entity_type, entity_id, provider, index, entry)


async def _ensure_person_link(db: AsyncSession, entity_id: Any, entity_type: str, creator: tuple[str, str], role: str) -> None:
    name, creator_role = creator
    result = await db.execute(select(Person).where(Person.name == name))
    person = result.scalar_one_or_none()
    if person is None:
        person = Person(name=name, metadata_json={"seed": True, "primary_role": creator_role})
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
    result = await db.execute(select(Tag).where(Tag.kind == entity_type.replace("_work", ""), Tag.name == tag_name))
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = Tag(kind=entity_type.replace("_work", ""), name=tag_name)
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
        arc = StoryArc(name=arc_name, description=f"Seed arc {arc_name}", publisher=None, metadata_json={"seed": True})
        db.add(arc)
        await db.flush()
    result = await db.execute(
        select(StoryArcItem).where(StoryArcItem.story_arc_id == arc.id, StoryArcItem.item_id == entity_id)
    )
    if result.scalar_one_or_none() is None:
        db.add(StoryArcItem(story_arc_id=arc.id, item_id=entity_id, ordinal=1))


async def _ensure_book_membership(db: AsyncSession, work_id: Any, series_id: Any, index: int) -> None:
    result = await db.execute(select(BookSeriesMembership).where(BookSeriesMembership.work_id == work_id, BookSeriesMembership.series_id == series_id))
    if result.scalar_one_or_none() is None:
        db.add(BookSeriesMembership(work_id=work_id, series_id=series_id, sequence=float(index), display_number=str(index), metadata_json={"seed": True}))


async def _ensure_comic_membership(db: AsyncSession, work_id: Any, series_id: Any, index: int) -> None:
    result = await db.execute(select(ComicSeriesMembership).where(ComicSeriesMembership.work_id == work_id, ComicSeriesMembership.series_id == series_id))
    if result.scalar_one_or_none() is None:
        db.add(ComicSeriesMembership(work_id=work_id, series_id=series_id, sequence=float(index), display_number=str(index), metadata_json={"seed": True}))


async def _ensure_manga_membership(db: AsyncSession, work_id: Any, series_id: Any, index: int) -> None:
    result = await db.execute(select(MangaSeriesMembership).where(MangaSeriesMembership.work_id == work_id, MangaSeriesMembership.series_id == series_id))
    if result.scalar_one_or_none() is None:
        db.add(MangaSeriesMembership(work_id=work_id, series_id=series_id, sequence=float(index), display_number=str(index), metadata_json={"seed": True}))


async def _ensure_character_appearance(db: AsyncSession, entity_id: Any, character_name: str | None, *, entity_type: str = "comic_work") -> None:
    if not character_name:
        return
    from app.models import Character, CharacterAppearance  # local import to avoid circulars in all files

    result = await db.execute(select(Character).where(Character.name == character_name))
    character = result.scalar_one_or_none()
    if character is None:
        character = Character(name=character_name, aliases=[f"{character_name} (seed)"], description=f"Seed character {character_name}", metadata_json={"seed": True})
        db.add(character)
        await db.flush()
    if entity_type == "anime_series":
        result = await db.execute(select(AnimeCharacterAppearance).where(AnimeCharacterAppearance.series_id == entity_id, AnimeCharacterAppearance.character_id == character.id))
        if result.scalar_one_or_none() is None:
            db.add(AnimeCharacterAppearance(series_id=entity_id, character_id=character.id, role="main"))
        return
    result = await db.execute(select(CharacterAppearance).where(CharacterAppearance.item_id == entity_id, CharacterAppearance.character_id == character.id))
    if result.scalar_one_or_none() is None:
        db.add(CharacterAppearance(item_id=entity_id, character_id=character.id, role="main"))


async def _ensure_story_arc_membership(db: AsyncSession, issue_id: Any, arc_name: str | None) -> None:
    if not arc_name:
        return
    result = await db.execute(select(StoryArc).where(StoryArc.name == arc_name))
    arc = result.scalar_one_or_none()
    if arc is None:
        arc = StoryArc(name=arc_name, description=f"Seed arc {arc_name}", publisher=None, metadata_json={"seed": True})
        db.add(arc)
        await db.flush()
    result = await db.execute(select(ComicStoryArcMembership).where(ComicStoryArcMembership.issue_id == issue_id, ComicStoryArcMembership.story_arc_id == arc.id))
    if result.scalar_one_or_none() is None:
        db.add(ComicStoryArcMembership(issue_id=issue_id, story_arc_id=arc.id, ordinal=1, metadata_json={"seed": True}))


async def _ensure_comic_links(db: AsyncSession, issue_id: Any, provider: ExternalProvider, index: int, entry: _Entry) -> None:
    await _ensure_provider(db, "comic_issue", issue_id, provider, index, entry)
    if entry.character:
        await _ensure_character_appearance(db, issue_id, entry.character)


async def _ensure_manga_links(db: AsyncSession, chapter_id: Any, provider: ExternalProvider, index: int, entry: _Entry) -> None:
    await _ensure_provider(db, "manga_chapter", chapter_id, provider, index, entry)
    if entry.character:
        await _ensure_character_appearance(db, chapter_id, entry.character, entity_type="manga_work")


async def _ensure_anime_links(db: AsyncSession, episode_id: Any, provider: ExternalProvider, index: int, entry: _Entry) -> None:
    await _ensure_provider(db, "anime_episode", episode_id, provider, index, entry)


async def _ensure_tv_links(db: AsyncSession, release_id: Any, provider: ExternalProvider, index: int, entry: _Entry) -> None:
    await _ensure_provider(db, "tv_release", release_id, provider, index, entry)


async def _ensure_book_links(db: AsyncSession, edition_id: Any, provider: ExternalProvider, index: int, entry: _Entry) -> None:
    await _ensure_provider(db, "book_edition", edition_id, provider, index, entry)


async def _delete_kind_rows(db: AsyncSession, entity_type: str, ids: list[Any]) -> None:
    if entity_type == "book_work":
        await db.execute(delete(BookSeriesMembership).where(BookSeriesMembership.work_id.in_(ids)))
        await db.execute(delete(BookContribution).where(BookContribution.work_id.in_(ids)))
        await db.execute(delete(BookEdition).where(BookEdition.work_id.in_(ids)))
        await db.execute(delete(BookWork).where(BookWork.id.in_(ids)))
    elif entity_type == "comic_work":
        await db.execute(delete(ComicSeriesMembership).where(ComicSeriesMembership.work_id.in_(ids)))
        await db.execute(delete(ComicStoryArcMembership).where(ComicStoryArcMembership.issue_id.in_(select(ComicIssue.id).where(ComicIssue.work_id.in_(ids)))))
        await db.execute(delete(ComicCharacterAppearance).where(ComicCharacterAppearance.issue_id.in_(select(ComicIssue.id).where(ComicIssue.work_id.in_(ids)))))
        await db.execute(delete(ComicContribution).where(ComicContribution.work_id.in_(ids)))
        await db.execute(delete(ComicIssue).where(ComicIssue.work_id.in_(ids)))
        await db.execute(delete(ComicWork).where(ComicWork.id.in_(ids)))
    elif entity_type == "manga_work":
        await db.execute(delete(MangaSeriesMembership).where(MangaSeriesMembership.work_id.in_(ids)))
        await db.execute(delete(MangaContribution).where(MangaContribution.work_id.in_(ids)))
        await db.execute(delete(MangaIdentifier).where(MangaIdentifier.work_id.in_(ids)))
        await db.execute(delete(MangaChapter).where(MangaChapter.work_id.in_(ids)))
        await db.execute(delete(MangaWork).where(MangaWork.id.in_(ids)))
    elif entity_type == "anime_series":
        await db.execute(delete(AnimeCharacterAppearance).where(AnimeCharacterAppearance.series_id.in_(ids)))
        await db.execute(delete(AnimeContribution).where(AnimeContribution.series_id.in_(ids)))
        await db.execute(delete(AnimeEpisode).where(AnimeEpisode.series_id.in_(ids)))
        await db.execute(delete(AnimeSeries).where(AnimeSeries.id.in_(ids)))
    elif entity_type == "movie_work":
        await db.execute(delete(MovieWorkIdentifier).where(MovieWorkIdentifier.work_id.in_(ids)))
        await db.execute(delete(MovieWorkContribution).where(MovieWorkContribution.work_id.in_(ids)))
        await db.execute(delete(MovieReleaseMedia).where(MovieReleaseMedia.release_id.in_(select(MovieRelease.id).where(MovieRelease.work_id.in_(ids)))))
        await db.execute(delete(MovieRelease).where(MovieRelease.work_id.in_(ids)))
        await db.execute(delete(MovieWork).where(MovieWork.id.in_(ids)))
    elif entity_type == "tv_release":
        await db.execute(delete(TVEpisode).where(TVEpisode.release_id.in_(ids)))
        await db.execute(delete(TVReleaseMedia).where(TVReleaseMedia.release_id.in_(ids)))
        await db.execute(delete(TVReleaseContribution).where(TVReleaseContribution.release_id.in_(ids)))
        await db.execute(delete(TVReleaseIdentifier).where(TVReleaseIdentifier.release_id.in_(ids)))
        await db.execute(delete(TVRelease).where(TVRelease.id.in_(ids)))
    elif entity_type == "music_release":
        await db.execute(delete(MusicTrack).where(MusicTrack.release_id.in_(ids)))
        await db.execute(delete(MusicMedia).where(MusicMedia.release_id.in_(ids)))
        await db.execute(delete(MusicReleaseContribution).where(MusicReleaseContribution.release_id.in_(ids)))
        await db.execute(delete(MusicReleaseIdentifier).where(MusicReleaseIdentifier.release_id.in_(ids)))
        await db.execute(delete(MusicRelease).where(MusicRelease.id.in_(ids)))
    elif entity_type == "game_work":
        await db.execute(delete(GameRelease).where(GameRelease.work_id.in_(ids)))
        await db.execute(delete(GameWork).where(GameWork.id.in_(ids)))
    elif entity_type == "boardgame_work":
        await db.execute(delete(BoardGameEdition).where(BoardGameEdition.work_id.in_(ids)))
        await db.execute(delete(BoardGameWork).where(BoardGameWork.id.in_(ids)))

