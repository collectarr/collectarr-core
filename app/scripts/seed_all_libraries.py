"""Seed a compact native dataset for all library kinds."""

from __future__ import annotations

import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.scripts.seed_native_catalog import seed_catalog, wipe_seed_data
from app.services.admin import AdminMetadataService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed one deterministic native entry for every library kind."
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Remove existing rows created by the native seed before writing.",
    )
    parser.add_argument(
        "--skip-search-reindex",
        action="store_true",
        help="Do not rebuild the Meilisearch catalog index after seeding.",
    )
    return parser.parse_args()


async def seed() -> None:
    args = parse_args()
    async with AsyncSessionLocal() as db:
        if args.wipe:
            removed = await wipe_seed_data(db)
            print(f"Removed {removed} existing native seed roots.")
        await seed_catalog(db, entries_per_kind=1)
        if not args.skip_search_reindex:
            result = await AdminMetadataService(db).reindex_search()
            if not result.ok:
                raise RuntimeError(
                    f"Search reindex failed after native seed: {result.error}"
                )
            print(f"Indexed {result.indexed_documents} catalog documents.")


if __name__ == "__main__":
    asyncio.run(seed())
