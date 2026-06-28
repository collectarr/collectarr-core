import asyncio
import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import Edition, ExternalProviderId, Franchise, Item, Series, Variant, Volume
from app.scripts.seed_cover_lookup import resolve_seed_cover_urls


@dataclass(frozen=True)
class SeedComic:
    franchise: str
    publisher: str
    series: str
    slug: str
    volume: str
    volume_number: int
    start_year: int
    item_number: str
    title: str
    synopsis: str
    release_date: date
    upc: str | None = None

    @property
    def sort_key(self) -> str:
        number = _issue_sort_segment(self.item_number)
        return f"{self.slug}-{number}"

    @property
    def provider_id(self) -> str:
        return f"seed-{self.slug}-{self.item_number.lower().replace(' ', '-')}"


SEED_COMICS = [
    SeedComic(
        franchise="Marvel",
        publisher="Marvel",
        series="The Amazing Spider-Man",
        slug="amazing-spider-man",
        volume="The Amazing Spider-Man (1963)",
        volume_number=1,
        start_year=1963,
        item_number="1",
        title="The Amazing Spider-Man",
        synopsis="Peter Parker steps into a new chapter as Spider-Man in this seed MVP record.",
        release_date=date(1963, 3, 1),
        upc="75960604716100111",
    ),
    SeedComic(
        franchise="Marvel",
        publisher="Marvel",
        series="The Amazing Spider-Man",
        slug="amazing-spider-man",
        volume="The Amazing Spider-Man (1963)",
        volume_number=1,
        start_year=1963,
        item_number="2",
        title="The Amazing Spider-Man",
        synopsis="A tense early issue built around public suspicion, danger, and Peter's double life.",
        release_date=date(1963, 5, 1),
    ),
    SeedComic(
        franchise="Marvel",
        publisher="Marvel",
        series="The Amazing Spider-Man",
        slug="amazing-spider-man",
        volume="The Amazing Spider-Man (1963)",
        volume_number=1,
        start_year=1963,
        item_number="3",
        title="The Amazing Spider-Man",
        synopsis="Spider-Man faces a brilliant new threat while trying to keep his personal world intact.",
        release_date=date(1963, 7, 1),
    ),
    SeedComic(
        franchise="Marvel",
        publisher="Marvel",
        series="The Amazing Spider-Man",
        slug="amazing-spider-man",
        volume="The Amazing Spider-Man (1963)",
        volume_number=1,
        start_year=1963,
        item_number="4",
        title="The Amazing Spider-Man",
        synopsis="A fast-moving street-level story with a new foe and a restless city.",
        release_date=date(1963, 9, 1),
    ),
    SeedComic(
        franchise="Marvel",
        publisher="Marvel",
        series="The Amazing Spider-Man",
        slug="amazing-spider-man",
        volume="The Amazing Spider-Man (1963)",
        volume_number=1,
        start_year=1963,
        item_number="5",
        title="The Amazing Spider-Man",
        synopsis="Peter balances school, money, and hero work while the stakes keep climbing.",
        release_date=date(1963, 10, 1),
    ),
    SeedComic(
        franchise="Marvel",
        publisher="Marvel",
        series="Ultimate Spider-Man",
        slug="ultimate-spider-man",
        volume="Ultimate Spider-Man (2000)",
        volume_number=1,
        start_year=2000,
        item_number="1",
        title="Ultimate Spider-Man",
        synopsis="A modernized origin issue for a new generation of Spider-Man readers.",
        release_date=date(2000, 10, 1),
    ),
    SeedComic(
        franchise="Marvel",
        publisher="Marvel",
        series="Ultimate Spider-Man",
        slug="ultimate-spider-man",
        volume="Ultimate Spider-Man (2000)",
        volume_number=1,
        start_year=2000,
        item_number="2",
        title="Ultimate Spider-Man",
        synopsis="Peter begins to understand the cost of power in a grounded modern continuity.",
        release_date=date(2000, 11, 1),
    ),
    SeedComic(
        franchise="DC",
        publisher="DC",
        series="Superman, Vol. 4",
        slug="superman-vol-4",
        volume="Superman, Vol. 4 (2016)",
        volume_number=4,
        start_year=2016,
        item_number="8A",
        title="Superman, Vol. 4",
        synopsis="Escape From Dinosaur Island, Part One.",
        release_date=date(2016, 10, 5),
        upc="76194134192700811",
    ),
    SeedComic(
        franchise="DC",
        publisher="DC",
        series="Superman, Vol. 4",
        slug="superman-vol-4",
        volume="Superman, Vol. 4 (2016)",
        volume_number=4,
        start_year=2016,
        item_number="9",
        title="Superman, Vol. 4",
        synopsis="The Dinosaur Island adventure continues with family stakes and strange terrain.",
        release_date=date(2016, 10, 19),
    ),
    SeedComic(
        franchise="DC",
        publisher="DC",
        series="Batman",
        slug="batman",
        volume="Batman (2016)",
        volume_number=3,
        start_year=2016,
        item_number="1",
        title="Batman",
        synopsis="A new Gotham era starts with impossible saves and a city watching closely.",
        release_date=date(2016, 6, 15),
        upc="76194134182800111",
    ),
    SeedComic(
        franchise="Image",
        publisher="Image",
        series="Saga",
        slug="saga",
        volume="Saga (2012)",
        volume_number=1,
        start_year=2012,
        item_number="1",
        title="Saga",
        synopsis="A sweeping space-fantasy family story begins with fugitives, war, and a newborn.",
        release_date=date(2012, 3, 14),
    ),
    SeedComic(
        franchise="Dark Horse",
        publisher="Dark Horse",
        series="Hellboy: Seed of Destruction",
        slug="hellboy-seed-of-destruction",
        volume="Hellboy: Seed of Destruction (1994)",
        volume_number=1,
        start_year=1994,
        item_number="1",
        title="Hellboy: Seed of Destruction",
        synopsis="A paranormal investigation opens into folklore, occult history, and old secrets.",
        release_date=date(1994, 3, 1),
    ),
]


def _issue_sort_segment(item_number: str) -> str:
    normalized = item_number.lower().replace("#", "").replace(" ", "")
    match = re.match(r"(?P<number>\d+)(?P<suffix>.*)", normalized)
    if match is None:
        return normalized
    return f"{int(match.group('number')):04d}{match.group('suffix')}"


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        franchises: dict[str, Franchise] = {}
        series_by_slug: dict[str, Series] = {}
        volumes_by_name: dict[str, Volume] = {}

        for comic in SEED_COMICS:
            franchise = franchises.get(comic.franchise)
            if franchise is None:
                franchise = await _get_or_create_franchise(db, comic.franchise)
                franchises[comic.franchise] = franchise

            series = series_by_slug.get(comic.slug)
            if series is None:
                series = await _get_or_create_series(db, comic, franchise)
                series_by_slug[comic.slug] = series

            volume = volumes_by_name.get(comic.volume)
            if volume is None:
                volume = await _get_or_create_volume(db, comic, series)
                volumes_by_name[comic.volume] = volume

            item = await _get_or_create_item(db, comic, volume)
            await _ensure_edition_and_variant(db, comic, item)
            await _ensure_provider_id(db, comic, item)

        await db.commit()


async def _get_or_create_franchise(db, name: str) -> Franchise:
    result = await db.execute(select(Franchise).where(Franchise.name == name))
    franchise = result.scalar_one_or_none()
    if franchise is not None:
        return franchise

    franchise = Franchise(name=name, description=f"{name} metadata seed.")
    db.add(franchise)
    await db.flush()
    return franchise


async def _get_or_create_series(db, comic: SeedComic, franchise: Franchise) -> Series:
    result = await db.execute(select(Series).where(Series.slug == comic.slug))
    series = result.scalar_one_or_none()
    if series is not None:
        return series

    series = Series(
        franchise=franchise,
        kind=ItemKind.comic,
        title=comic.series,
        slug=comic.slug,
        description=f"Seed data for {comic.series}.",
    )
    db.add(series)
    await db.flush()
    return series


async def _get_or_create_volume(db, comic: SeedComic, series: Series) -> Volume:
    result = await db.execute(select(Volume).where(Volume.name == comic.volume))
    volume = result.scalar_one_or_none()
    if volume is not None:
        return volume

    volume = Volume(
        series=series,
        name=comic.volume,
        volume_number=comic.volume_number,
        start_year=comic.start_year,
    )
    db.add(volume)
    await db.flush()
    return volume


async def _get_or_create_item(db, comic: SeedComic, volume: Volume) -> Item:
    result = await db.execute(
        select(Item).where(
            Item.volume_id == volume.id,
            Item.item_number == comic.item_number,
            Item.kind == ItemKind.comic,
        )
    )
    item = result.scalar_one_or_none()
    if item is not None:
        item.title = comic.title
        item.sort_key = comic.sort_key
        item.synopsis = comic.synopsis
        return item

    item = Item(
        volume=volume,
        kind=ItemKind.comic,
        title=comic.title,
        item_number=comic.item_number,
        sort_key=comic.sort_key,
        synopsis=comic.synopsis,
    )
    db.add(item)
    await db.flush()
    return item


async def _ensure_edition_and_variant(db, comic: SeedComic, item: Item) -> None:
    result = await db.execute(select(Edition).where(Edition.item_id == item.id))
    edition = result.scalar_one_or_none()
    if edition is None:
        edition = Edition(
            item=item,
            title="Standard Edition",
            format="Single Issue",
            publisher=comic.publisher,
            language="en",
            release_date=comic.release_date,
        )
        db.add(edition)
        await db.flush()
    else:
        edition.title = "Standard Edition"
        edition.format = "Single Issue"
        edition.publisher = comic.publisher
        edition.language = "en"
        edition.release_date = comic.release_date
    edition.upc = comic.upc

    result = await db.execute(select(Variant).where(Variant.edition_id == edition.id))
    variant = result.scalar_one_or_none()
    cover_url, thumbnail_url = await resolve_seed_cover_urls(
        kind=ItemKind.comic,
        slug=comic.slug,
        title=comic.title,
        series=comic.series,
        fallback_key=f"collectarr-comic-{comic.slug}-{comic.item_number}",
    )
    if variant is None:
        variant = Variant(
            edition=edition,
            name="Cover A",
            is_primary=True,
            cover_image_url=cover_url,
            thumbnail_image_url=thumbnail_url,
        )
        db.add(variant)
    else:
        variant.name = "Cover A"
        variant.is_primary = True
        variant.cover_image_url = cover_url
        variant.thumbnail_image_url = thumbnail_url


async def _ensure_provider_id(db, comic: SeedComic, item: Item) -> None:
    result = await db.execute(
        select(ExternalProviderId).where(
            ExternalProviderId.provider == ExternalProvider.comicvine,
            ExternalProviderId.provider_item_id == comic.provider_id,
            ExternalProviderId.entity_type == "item",
        )
    )
    if result.scalar_one_or_none() is not None:
        return

    db.add(
        ExternalProviderId(
            provider=ExternalProvider.comicvine,
            provider_item_id=comic.provider_id,
            entity_type="item",
            entity_id=item.id,
        )
    )


if __name__ == "__main__":
    asyncio.run(seed())
