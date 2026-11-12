"""Game identity rules shared by catalog writes and the release upgrade."""

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.catalog_game_item import GameItem

# These identify a particular release rather than just the game. A title or a
# platform alone is deliberately insufficient to guess an edition or merge games.
EDITION_FIELDS = frozenset({
    "barcode", "catalog_number", "edition_title", "variant_name",
    "release_region", "physical_format", "physical_format_label",
})
EDITION_ONLY_FIELDS = EDITION_FIELDS | {
    "identifiers", "cover_image_url", "thumbnail_image_url", "game_id", "media_id",
}


def is_game_edition(document: Mapping[str, Any]) -> bool:
    return any(isinstance(document.get(key), str) and document[key].strip()
               for key in EDITION_FIELDS)


def game_level_document(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key not in EDITION_ONLY_FIELDS}


def game_record_for_edition(document: Mapping[str, Any]) -> GameItem:
    game = game_level_document(document)
    return GameItem(title=game.pop("title").strip(), sort_key=game.pop("sort_key", None), details=game)


async def migrate_game_identities(connection: AsyncConnection, schema: str) -> None:
    """Upgrade released game rows without changing IDs or guessing title matches."""
    table = '"' + schema.replace('"', '""') + '".game_items'
    columns = await connection.run_sync(
        lambda conn: {column["name"] for column in inspect(conn).get_columns("game_items", schema=schema)}
    )
    if "parent_game_id" not in columns:
        await connection.execute(text(f"ALTER TABLE {table} ADD COLUMN parent_game_id uuid"))
        await connection.execute(text(
            f"ALTER TABLE {table} ADD CONSTRAINT fk_game_items_parent_game_id "
            f"FOREIGN KEY (parent_game_id) REFERENCES {table}(id) ON DELETE RESTRICT"
        ))
        await connection.execute(text(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_game_items_not_own_parent "
            "CHECK (parent_game_id IS NULL OR parent_game_id <> id)"
        ))
        await connection.execute(text(
            f"CREATE INDEX ix_game_items_parent_game_id ON {table} (parent_game_id)"
        ))

    rows = (await connection.execute(
        select(GameItem.__table__).where(GameItem.parent_game_id.is_(None))
    )).mappings().all()
    for row in rows:
        document = {**row["details"], "title": row["title"],
                    "barcode": row["barcode"], "catalog_number": row["catalog_number"]}
        if not is_game_edition(document):
            continue
        game_id = uuid4()
        await connection.execute(GameItem.__table__.insert().values(
            id=game_id, title=row["title"], sort_key=row["sort_key"],
            details=game_level_document(document), revision=1,
        ))
        await connection.execute(GameItem.__table__.update()
            .where(GameItem.id == row["id"])
            .values(parent_game_id=game_id, updated_at=row["updated_at"]))
