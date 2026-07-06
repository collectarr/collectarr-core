from __future__ import annotations

import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.services.importers.clz.clz_comics_xml_importer import ClzComicsXmlImporter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import CLZ Comics XML into Collectarr.")
    parser.add_argument("path", help="Path to the CLZ Comics XML file")
    return parser.parse_args()


async def main_async(path: str) -> int:
    with open(path, encoding="utf-8") as handle:
        xml_text = handle.read()
    async with AsyncSessionLocal() as db:
        importer = ClzComicsXmlImporter()
        imported = await importer.import_xml(db, xml_text)
    print(f"Imported {imported} comic record(s).")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args.path))


if __name__ == "__main__":
    raise SystemExit(main())
