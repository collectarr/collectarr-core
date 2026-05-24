from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from urllib.parse import urlparse

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.models.canonical import Edition, Item, Series, Variant, Volume
from app.providers.comicvine import ComicVineIssueCover, ComicVineProvider
from app.search.client import SearchClient
from app.search.documents import item_search_document


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enrich comic cover URLs with ComicVine image URLs. Useful when "
            "bibliographic providers return cover URLs that are not hotlinkable."
        )
    )
    parser.add_argument("--series", help="Limit enrichment to a series title.")
    parser.add_argument("--issue", help="Limit enrichment to a single issue number.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum items to inspect.")
    parser.add_argument(
        "--replace-gcd-covers",
        action="store_true",
        help="Replace covers hosted on comics.org, even when the URL is present.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace every matched cover URL with the ComicVine issue cover.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing.")
    return parser.parse_args(argv)


async def run_enrich(
    args: argparse.Namespace, emit: Callable[[str], None] = print
) -> int:
    provider = ComicVineProvider()
    if not provider.is_configured:
        emit("ComicVine is not configured. Set COMICVINE_API_KEY before running.")
        return 2

    async with AsyncSessionLocal() as db:
        items = await _load_items(db, args)
        changed_items: list[Item] = []
        cover_cache: dict[tuple[str, str, int | None], ComicVineIssueCover | None] = {}

        for item in items:
            target_variants = _target_variants(
                item,
                replace_gcd_covers=args.replace_gcd_covers,
                force=args.force,
            )
            if not target_variants:
                continue

            series_title = _series_title(item)
            issue_number = item.item_number
            if not series_title or not issue_number:
                emit(f"SKIPPED item_id={item.id} missing series or issue number")
                continue

            start_year = _start_year(item)
            cache_key = (series_title, issue_number, start_year)
            if cache_key not in cover_cache:
                cover_cache[cache_key] = await provider.find_issue_cover(
                    series_title=series_title,
                    issue_number=issue_number,
                    start_year=start_year,
                )
            cover = cover_cache[cache_key]
            if cover is None:
                emit(
                    "SKIPPED "
                    f"item_id={item.id} {series_title} #{issue_number} no ComicVine cover match"
                )
                continue

            if args.dry_run:
                emit(
                    "DRY-RUN "
                    f"item_id={item.id} {series_title} #{issue_number} "
                    f"variants={len(target_variants)} cover={cover.image_url}"
                )
                continue

            for variant in target_variants:
                variant.cover_image_url = cover.image_url
                if _is_gcd_cover(variant.thumbnail_image_url):
                    variant.thumbnail_image_url = None
            changed_items.append(item)
            emit(
                "UPDATED "
                f"item_id={item.id} {series_title} #{issue_number} "
                f"variants={len(target_variants)} comicvine={cover.provider_item_id}"
            )

        if args.dry_run:
            emit("Dry run complete.")
            return 0

        if changed_items:
            documents = [item_search_document(item) for item in changed_items]
            await db.commit()
            await SearchClient().index_documents_best_effort(documents)
        else:
            await db.rollback()
        emit(f"Updated {len(changed_items)} item(s).")
        return 0


async def _load_items(db: AsyncSession, args: argparse.Namespace) -> list[Item]:
    stmt = _item_stmt().where(Item.kind == ItemKind.comic).limit(args.limit)
    if args.series:
        pattern = f"%{args.series.strip()}%"
        stmt = (
            stmt.join(Item.volume, isouter=True)
            .join(Volume.series, isouter=True)
            .where(
                or_(
                    Item.title.ilike(pattern),
                    Volume.name.ilike(pattern),
                    Series.title.ilike(pattern),
                )
            )
        )
    if args.issue:
        stmt = stmt.where(Item.item_number == args.issue.strip())
    result = await db.execute(stmt)
    return list(result.scalars().unique())


def _item_stmt() -> Select[tuple[Item]]:
    return (
        select(Item)
        .options(
            selectinload(Item.volume).selectinload(Volume.series),
            selectinload(Item.editions).selectinload(Edition.variants),
        )
        .order_by(Item.sort_key.nullslast(), Item.title)
    )


def _target_variants(
    item: Item, *, replace_gcd_covers: bool, force: bool
) -> list[Variant]:
    targets: list[Variant] = []
    for edition in item.editions:
        for variant in edition.variants:
            cover_url = variant.cover_image_url
            if force or not cover_url or (replace_gcd_covers and _is_gcd_cover(cover_url)):
                targets.append(variant)
    return targets


def _series_title(item: Item) -> str | None:
    if item.volume and item.volume.name:
        return item.volume.name
    return item.title


def _start_year(item: Item) -> int | None:
    if item.volume and item.volume.start_year:
        return item.volume.start_year
    for edition in item.editions:
        if edition.release_date:
            return edition.release_date.year
    return None


def _is_gcd_cover(url: str | None) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.casefold()
    return host.endswith("comics.org")


def main() -> None:
    raise SystemExit(asyncio.run(run_enrich(parse_args())))


if __name__ == "__main__":
    main()
