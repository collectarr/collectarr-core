"""Seed a richer native dataset for all library kinds."""

from __future__ import annotations

import argparse
import asyncio

from app.db.session import AsyncSessionLocal, engine
from app.models import Base
from app.scripts.seed_native_catalog import seed_catalog, wipe_seed_data
from app.services.admin import AdminMetadataService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the deterministic native showcase catalog."
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Remove existing rows created by the native seed before writing.",
    )
    parser.add_argument(
        "--entries-per-kind",
        type=int,
        default=2,
        choices=(1, 2),
        help="Number of showcase entries to write for each kind (default: 2).",
    )
    parser.add_argument(
        "--skip-search-reindex",
        action="store_true",
        help="Do not rebuild the Meilisearch catalog index after seeding.",
    )
    return parser.parse_args()


async def seed() -> None:
    args = parse_args()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        if args.wipe:
            await wipe_seed_data(db)
        await seed_catalog(db, entries_per_kind=args.entries_per_kind)
        if not args.skip_search_reindex:
            result = await AdminMetadataService(db).reindex_search()
            if not result.ok:
                raise RuntimeError(
                    f"Search reindex failed after native seed: {result.error}"
                )
            print(f"Indexed {result.indexed_documents} catalog documents.")


if __name__ == "__main__":
    asyncio.run(seed())
