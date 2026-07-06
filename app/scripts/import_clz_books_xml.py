from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.database import async_session
from app.services.importers.clz.clz_books_xml_importer import ClzBooksXmlImporter


async def _run(path: Path) -> int:
    xml_text = path.read_text(encoding="utf-8")
    importer = ClzBooksXmlImporter()
    async with async_session() as db:
        return await importer.import_xml(db, xml_text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CLZ Books XML into Collectarr.")
    parser.add_argument("path", help="Path to the CLZ Books XML file")
    args = parser.parse_args()
    count = asyncio.run(_run(Path(args.path)))
    print(f"Imported {count} book record(s).")


if __name__ == "__main__":
    main()
