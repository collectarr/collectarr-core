from __future__ import annotations

import argparse
import asyncio
import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models import (
    ComicIdentifier,
    ComicIssue,
    ComicVolume,
    ComicWork,
    ExternalProviderId,
)
from app.models.base import ExternalProvider, ItemKind
from app.scripts.seed_cover_lookup import resolve_seed_cover_urls
from app.search.client import SearchClient
from app.search.documents import comic_work_search_document


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

    @property
    def provider_id(self) -> str:
        return f"seed-{self.slug}-{self.issue_number.lower().replace(' ', '-')}"


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
    normalized = issue_number.lower().replace("#", "").replace(" ", "")
    match = re.match(r"(?P<number>\d+)(?P<suffix>.*)", normalized)
    if match is None:
        return normalized
    return f"{int(match.group('number')):04d}{match.group('suffix')}"


def _sort_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized or value.casefold()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed v1 comic works and issues.")
    return parser.parse_args(argv)


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        changed_work_ids: set[UUID] = set()
        for comic in SEED_COMICS:
            volume = await _get_or_create_volume(db, comic)
            work = await _get_or_create_work(db, comic, volume)
            await _upsert_issue(db, comic, work)
            changed_work_ids.add(work.id)

        await db.commit()
        if not changed_work_ids:
            return

        result = await db.execute(
            select(ComicWork)
            .where(ComicWork.id.in_(changed_work_ids))
            .options(
                selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                selectinload(ComicWork.issues).selectinload(ComicIssue.contributions),
                selectinload(ComicWork.issues).selectinload(ComicIssue.character_appearances),
                selectinload(ComicWork.issues).selectinload(ComicIssue.story_arc_memberships),
            )
        )
        works = list(result.scalars().unique())
        if works:
            await SearchClient().index_documents_best_effort(
                [comic_work_search_document(work) for work in works]
            )


async def _get_or_create_volume(db: AsyncSession, comic: SeedComicIssue) -> ComicVolume:
    result = await db.execute(select(ComicVolume).where(ComicVolume.title == comic.work_title))
    volume = result.scalar_one_or_none()
    if volume is not None:
        return volume

    volume = ComicVolume(title=comic.work_title, slug=_sort_key(comic.work_title), start_year=comic.release_date.year)
    db.add(volume)
    await db.flush()
    return volume


async def _get_or_create_work(db: AsyncSession, comic: SeedComicIssue, volume: ComicVolume) -> ComicWork:
    result = await db.execute(select(ComicWork).where(ComicWork.title == comic.work_title))
    work = result.scalar_one_or_none()
    if work is None:
        work = ComicWork(
            volume=volume,
            title=comic.work_title,
            sort_title=_sort_key(comic.work_title),
            description=f"Seed data for {comic.work_title}.",
            original_language="en",
            first_publication_date=comic.release_date,
        )
        db.add(work)
        await db.flush()
        return work

    work.sort_title = _sort_key(comic.work_title)
    work.description = f"Seed data for {comic.work_title}."
    work.original_language = "en"
    if work.volume is None:
        work.volume = volume
    if work.first_publication_date is None or comic.release_date < work.first_publication_date:
        work.first_publication_date = comic.release_date
    return work


async def _upsert_issue(db: AsyncSession, comic: SeedComicIssue, work: ComicWork) -> ComicIssue:
    result = await db.execute(
        select(ComicIssue).where(
            ComicIssue.work_id == work.id,
            ComicIssue.issue_number == comic.issue_number,
        )
    )
    issue = result.scalar_one_or_none()
    cover_url, _thumbnail_url = await resolve_seed_cover_urls(
        kind=ItemKind.comic,
        slug=comic.slug,
        title=comic.title,
        series=comic.work_title,
        fallback_key=f"collectarr-comic-{comic.slug}-{comic.issue_number}",
    )
    metadata_json: dict[str, Any] = {
        "provider": ExternalProvider.comicvine.value,
        "provider_item_id": comic.provider_id,
        "normalized": {
            "title": comic.title,
            "issue_number": comic.issue_number,
            "release_date": comic.release_date.isoformat(),
            "publisher": comic.publisher,
        },
    }
    if issue is None:
        issue = ComicIssue(
            work=work,
            issue_number=comic.issue_number,
            display_title=comic.title,
            publication_date=comic.release_date,
            release_date=comic.release_date,
            publisher=comic.publisher,
            language="en",
            region="US",
            release_status="released",
            cover_image_url=cover_url,
            description=comic.synopsis,
            metadata_json=metadata_json,
        )
        db.add(issue)
        await db.flush()
    else:
        issue.display_title = comic.title
        issue.publication_date = comic.release_date
        issue.release_date = comic.release_date
        issue.publisher = comic.publisher
        issue.language = "en"
        issue.region = "US"
        issue.release_status = "released"
        issue.cover_image_url = cover_url
        issue.description = comic.synopsis
        issue.metadata_json = metadata_json

    await _ensure_identifier(
        db,
        issue,
        identifier_type="provider_item_id",
        value=comic.provider_id,
        source_provider=ExternalProvider.comicvine,
        is_primary=True,
    )
    if comic.upc:
        await _ensure_identifier(
            db,
            issue,
            identifier_type="upc",
            value=comic.upc,
            source_provider=ExternalProvider.comicvine,
            is_primary=False,
        )
    await _ensure_provider_id(db, issue, comic.provider_id)
    return issue


async def _ensure_identifier(
    db: AsyncSession,
    issue: ComicIssue,
    *,
    identifier_type: str,
    value: str,
    source_provider: ExternalProvider | None,
    is_primary: bool,
) -> None:
    normalized_value = re.sub(r"\D+", "", value) or value.strip()
    result = await db.execute(
        select(ComicIdentifier).where(
            ComicIdentifier.issue_id == issue.id,
            ComicIdentifier.identifier_type == identifier_type,
            ComicIdentifier.normalized_value == normalized_value,
        )
    )
    identifier = result.scalar_one_or_none()
    if identifier is None:
        db.add(
            ComicIdentifier(
                issue=issue,
                identifier_type=identifier_type,
                value=value,
                normalized_value=normalized_value,
                is_primary=is_primary,
                source_provider=source_provider,
            )
        )
        return

    identifier.value = value
    identifier.normalized_value = normalized_value
    identifier.is_primary = is_primary
    identifier.source_provider = source_provider


async def _ensure_provider_id(db: AsyncSession, issue: ComicIssue, provider_item_id: str) -> None:
    result = await db.execute(
        select(ExternalProviderId).where(
            ExternalProviderId.provider == ExternalProvider.comicvine,
            ExternalProviderId.provider_item_id == provider_item_id,
            ExternalProviderId.entity_type == "comic_issue",
        )
    )
    if result.scalar_one_or_none() is not None:
        return

    db.add(
        ExternalProviderId(
            provider=ExternalProvider.comicvine,
            provider_item_id=provider_item_id,
            entity_type="comic_issue",
            entity_id=issue.id,
        )
    )


def main(argv: list[str] | None = None) -> None:
    parse_args(argv)
    asyncio.run(seed())


if __name__ == "__main__":
    main()
