"""Split typed metadata into per-kind inherited tables.

Revision ID: 20260624_0002
Revises: 20260624_0001
Create Date: 2026-06-24 12:18:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260624_0002"
down_revision: str | None = "20260624_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_KINDS = (
    "anime",
    "boardgame",
    "book",
    "bluray",
    "collection",
    "comic",
    "game",
    "manga",
    "movie",
    "music",
    "tv",
)


def upgrade() -> None:
    for kind in _KINDS:
        op.execute(
            sa.text(
                f"""
                CREATE TABLE IF NOT EXISTS item_kind_metadata_{kind} (
                    CHECK (kind = '{kind}')
                ) INHERITS (item_kind_metadata)
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_item_kind_metadata_{kind}_item_id
                ON item_kind_metadata_{kind} (item_id)
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE INDEX IF NOT EXISTS ix_item_kind_metadata_{kind}_id
                ON item_kind_metadata_{kind} (id)
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                INSERT INTO item_kind_metadata_{kind}
                SELECT * FROM item_kind_metadata
                WHERE kind = '{kind}'
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DELETE FROM ONLY item_kind_metadata
                WHERE kind = '{kind}'
                """
            )
        )

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION route_item_kind_metadata_insert()
            RETURNS trigger AS $$
            BEGIN
                IF NEW.kind = 'anime' THEN
                    INSERT INTO item_kind_metadata_anime VALUES (NEW.*);
                ELSIF NEW.kind = 'boardgame' THEN
                    INSERT INTO item_kind_metadata_boardgame VALUES (NEW.*);
                ELSIF NEW.kind = 'book' THEN
                    INSERT INTO item_kind_metadata_book VALUES (NEW.*);
                ELSIF NEW.kind = 'bluray' THEN
                    INSERT INTO item_kind_metadata_bluray VALUES (NEW.*);
                ELSIF NEW.kind = 'collection' THEN
                    INSERT INTO item_kind_metadata_collection VALUES (NEW.*);
                ELSIF NEW.kind = 'comic' THEN
                    INSERT INTO item_kind_metadata_comic VALUES (NEW.*);
                ELSIF NEW.kind = 'game' THEN
                    INSERT INTO item_kind_metadata_game VALUES (NEW.*);
                ELSIF NEW.kind = 'manga' THEN
                    INSERT INTO item_kind_metadata_manga VALUES (NEW.*);
                ELSIF NEW.kind = 'movie' THEN
                    INSERT INTO item_kind_metadata_movie VALUES (NEW.*);
                ELSIF NEW.kind = 'music' THEN
                    INSERT INTO item_kind_metadata_music VALUES (NEW.*);
                ELSIF NEW.kind = 'tv' THEN
                    INSERT INTO item_kind_metadata_tv VALUES (NEW.*);
                ELSE
                    RAISE EXCEPTION 'Unsupported item kind metadata route: %', NEW.kind;
                END IF;
                RETURN NULL;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER tr_item_kind_metadata_insert_router
            BEFORE INSERT ON item_kind_metadata
            FOR EACH ROW EXECUTE FUNCTION route_item_kind_metadata_insert()
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS tr_item_kind_metadata_insert_router ON item_kind_metadata"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS route_item_kind_metadata_insert()"))

    for kind in _KINDS:
        op.execute(
            sa.text(
                f"""
                INSERT INTO item_kind_metadata
                SELECT * FROM item_kind_metadata_{kind}
                """
            )
        )
        op.execute(sa.text(f"DROP TABLE IF EXISTS item_kind_metadata_{kind}"))
