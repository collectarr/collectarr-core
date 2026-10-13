from __future__ import annotations

import argparse
import asyncio
import re
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import (
    ComicItem,
)
from app.models.base import ItemKind
from app.scripts.seed_cover_lookup import resolve_seed_cover_urls
from app.search.client import SearchClient
from app.search.documents import catalog_search_document


@dataclass(frozen=True)
class SeedComicIssue:
    publisher: str
    work_title: str
    slug: str
    issue_number: str
    title: str
    synopsis: str
    release_date: date
    upc: str | None = None

    @property
    def sort_key(self) -> str:
        number = _issue_sort_segment(self.issue_number)
        return f"{self.slug}-{number}"

SEED_COMICS = [
    SeedComicIssue(
        publisher="Marvel",
        work_title="The Amazing Spider-Man",
        slug="amazing-spider-man",
        issue_number="1",
        title="The Amazing Spider-Man",
        synopsis="Peter Parker steps into a new chapter as Spider-Man in this seed issue.",
        release_date=date(1963, 3, 1),
        upc="75960604716100111",
    ),
    SeedComicIssue(
        publisher="Marvel",
        work_title="The Amazing Spider-Man",
        slug="amazing-spider-man",
        issue_number="2",
        title="The Amazing Spider-Man",
        synopsis="A tense early issue built around public suspicion, danger, and Peter's double life.",
        release_date=date(1963, 5, 1),
    ),
    SeedComicIssue(
        publisher="Marvel",
        work_title="The Amazing Spider-Man",
        slug="amazing-spider-man",
        issue_number="3",
        title="The Amazing Spider-Man",
        synopsis="Spider-Man faces a brilliant new threat while trying to keep his personal world intact.",
        release_date=date(1963, 7, 1),
    ),
    SeedComicIssue(
        publisher="Marvel",
        work_title="The Amazing Spider-Man",
        slug="amazing-spider-man",
        issue_number="4",
        title="The Amazing Spider-Man",
        synopsis="A fast-moving street-level story with a new foe and a restless city.",
        release_date=date(1963, 9, 1),
    ),
    SeedComicIssue(
        publisher="Marvel",
        work_title="The Amazing Spider-Man",
        slug="amazing-spider-man",
        issue_number="5",
        title="The Amazing Spider-Man",
        synopsis="Peter balances school, money, and hero work while the stakes keep climbing.",
        release_date=date(1963, 10, 1),
    ),
    SeedComicIssue(
        publisher="Marvel",
        work_title="Ultimate Spider-Man",
        slug="ultimate-spider-man",
        issue_number="1",
        title="Ultimate Spider-Man",
        synopsis="A modernized origin issue for a new generation of Spider-Man readers.",
        release_date=date(2000, 10, 1),
    ),
    SeedComicIssue(
        publisher="Marvel",
        work_title="Ultimate Spider-Man",
        slug="ultimate-spider-man",
        issue_number="2",
        title="Ultimate Spider-Man",
        synopsis="Peter begins to understand the cost of power in a grounded modern continuity.",
        release_date=date(2000, 11, 1),
    ),
    SeedComicIssue(
        publisher="DC",
        work_title="Superman, Vol. 4",
        slug="superman-vol-4",
        issue_number="8A",
        title="Superman, Vol. 4",
        synopsis="Escape From Dinosaur Island, Part One.",
        release_date=date(2016, 10, 5),
        upc="76194134192700811",
    ),
    SeedComicIssue(
        publisher="DC",
        work_title="Superman, Vol. 4",
        slug="superman-vol-4",
        issue_number="9",
        title="Superman, Vol. 4",
        synopsis="The Dinosaur Island adventure continues with family stakes and strange terrain.",
        release_date=date(2016, 10, 19),
    ),
    SeedComicIssue(
        publisher="DC",
        work_title="Batman",
        slug="batman",
        issue_number="1",
        title="Batman",
        synopsis="A new Gotham era starts with impossible saves and a city watching closely.",
        release_date=date(2016, 6, 15),
        upc="76194134182800111",
    ),
    SeedComicIssue(
        publisher="Image",
        work_title="Saga",
        slug="saga",
        issue_number="1",
        title="Saga",
        synopsis="A sweeping space-fantasy family story begins with fugitives, war, and a newborn.",
        release_date=date(2012, 3, 14),
    ),
    SeedComicIssue(
        publisher="Dark Horse",
        work_title="Hellboy: Seed of Destruction",
        slug="hellboy-seed-of-destruction",
        issue_number="1",
        title="Hellboy: Seed of Destruction",
        synopsis="A paranormal investigation opens into folklore, occult history, and old secrets.",
        release_date=date(1994, 3, 1),
    ),
]


def _issue_sort_segment(issue_number: str) -> str:
    normalized = issue_number.casefold().replace("#", "").replace(" ", "")
    match = re.match(r"(?P<number>\d+)(?P<suffix>.*)", normalized)
    if match is None:
        return normalized
    return f"{int(match.group('number')):04d}{match.group('suffix')}"


def _sort_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized or value.casefold()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Comic Catalog Items.")
    return parser.parse_args(argv)


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        changed_items: list[ComicItem] = []
        for comic in SEED_COMICS:
            changed_items.append(await _upsert_item(db, comic))

        await db.commit()
        if changed_items:
            await SearchClient().index_documents_best_effort(
                [catalog_search_document(item) for item in changed_items]
            )


async def _upsert_item(db: AsyncSession, comic: SeedComicIssue) -> ComicItem:
    item_title = f"{comic.work_title} #{comic.issue_number}"
    result = await db.execute(select(ComicItem).where(ComicItem.title == item_title))
    item = result.scalar_one_or_none()
    cover_url, _thumbnail_url = await resolve_seed_cover_urls(
        kind=ItemKind.comic,
        slug=comic.slug,
        title=comic.title,
        series=comic.work_title,
        fallback_key=f"collectarr-comic-{comic.slug}-{comic.issue_number}",
    )
    if item is None:
        item = ComicItem(title=item_title, sort_key=comic.sort_key, details={})
        db.add(item)
        await db.flush()
    item.title = item_title
    item.sort_key = comic.sort_key
    item.barcode = comic.upc
    item.catalog_number = None
    item.details = {
        **dict(item.details or {}),
        "series_title": comic.work_title,
        "issue_number": comic.issue_number,
        "release_date": comic.release_date.isoformat(),
        "release_date_parts": {
            "year": comic.release_date.year,
            "month": comic.release_date.month,
            "day": comic.release_date.day,
        },
        "publisher": comic.publisher,
        "language": "en",
        "country": "US",
        "release_status": "released",
        "description": comic.synopsis,
        "cover_image_url": cover_url,
    }

    if comic.upc:
        normalized_value = re.sub(r"\D+", "", comic.upc) or comic.upc.strip()
        identifiers = list(item.details.get("identifiers") or [])
        identifier = next(
            (
                value
                for value in identifiers
                if value.get("identifier_type") == "upc"
                and value.get("normalized_value") == normalized_value
            ),
            None,
        )
        if identifier is None:
            identifiers.append(
                {
                    "id": str(uuid4()),
                    "identifier_type": "upc",
                    "value": comic.upc,
                    "normalized_value": normalized_value,
                    "is_primary": False,
                }
            )
        else:
            identifier["value"] = comic.upc
        item.details = {**item.details, "identifiers": identifiers}
    await db.flush()
    return item


def main(argv: list[str] | None = None) -> None:
    parse_args(argv)
    asyncio.run(seed())


if __name__ == "__main__":
    main()
