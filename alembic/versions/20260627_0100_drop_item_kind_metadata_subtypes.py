"""Drop item_kind_metadata subtype tables.

Revision ID: 20260627_0100
Revises: 20260627_0001
Create Date: 2026-06-27 01:00:00.000000
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260627_0100"
down_revision: str | None = "20260627_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("item_kind_metadata", "metadata_json"):
        op.add_column("item_kind_metadata", sa.Column("metadata_json", JSONB(), nullable=True))

    bind = op.get_bind()
    metadata_rows = bind.execute(
        sa.text("SELECT id, metadata_json FROM item_kind_metadata")
    ).mappings().all()
    metadata_by_id: dict[object, dict[str, object]] = {}
    for row in metadata_rows:
        existing = row["metadata_json"]
        metadata_by_id[row["id"]] = dict(existing) if isinstance(existing, dict) else {}

    taxonomy_rows = bind.execute(
        sa.text(
            """
            SELECT
                ikmt.item_kind_metadata_id AS metadata_id,
                ikmt.category,
                mt.name,
                ikmt.position
            FROM item_kind_metadata_taxonomies ikmt
            JOIN metadata_taxonomies mt ON mt.id = ikmt.taxonomy_id
            ORDER BY ikmt.item_kind_metadata_id, ikmt.category, ikmt.position, ikmt.created_at, ikmt.id
            """
        )
    ).mappings().all()
    taxonomy_values: dict[object, dict[str, list[str]]] = defaultdict(
        lambda: {"genres": [], "platforms": []}
    )
    for row in taxonomy_rows:
        metadata_id = row["metadata_id"]
        name = str(row["name"] or "").strip()
        if not name:
            continue
        bucket = taxonomy_values[metadata_id]
        category = str(row["category"] or "")
        key = "genres" if category == "genre" else "platforms" if category == "platform" else None
        if key is None:
            continue
        values = bucket[key]
        if name.casefold() not in {entry.casefold() for entry in values}:
            values.append(name)

    music_rows = bind.execute(
        sa.text(
            """
            SELECT
                m.id AS metadata_id,
                m.track_count,
                t.title,
                t.position,
                t.duration_seconds,
                t.artist,
                t.disc_number
            FROM item_kind_metadata_music m
            LEFT JOIN item_kind_metadata_music_tracks t ON t.item_kind_metadata_id = m.id
            ORDER BY m.id, t.disc_number NULLS LAST, t.position NULLS LAST, t.created_at, t.id
            """
        )
    ).mappings().all()
    music_values: dict[object, dict[str, object]] = {}
    for row in music_rows:
        metadata_id = row["metadata_id"]
        payload = music_values.setdefault(metadata_id, {"tracks": []})
        track_count = row["track_count"]
        if track_count is not None:
            payload["track_count"] = int(track_count)
        title = str(row["title"] or "").strip()
        if not title:
            continue
        track = {"title": title}
        for key in ("position", "duration_seconds", "artist", "disc_number"):
            value = row[key]
            if value is not None:
                track[key] = value
        payload["tracks"].append(track)

    color_rows = bind.execute(
        sa.text(
            """
            SELECT id AS metadata_id, color FROM item_kind_metadata_anime
            UNION ALL
            SELECT id AS metadata_id, color FROM item_kind_metadata_movie
            UNION ALL
            SELECT id AS metadata_id, color FROM item_kind_metadata_tv
            """
        )
    ).mappings().all()
    color_values: dict[object, str] = {}
    for row in color_rows:
        color = str(row["color"] or "").strip()
        if color:
            color_values[row["metadata_id"]] = color

    for metadata_id, metadata_json in metadata_by_id.items():
        taxonomy = taxonomy_values.get(metadata_id)
        if taxonomy:
            if taxonomy["genres"]:
                metadata_json["genres"] = taxonomy["genres"]
            if taxonomy["platforms"]:
                metadata_json["platforms"] = taxonomy["platforms"]
        music = music_values.get(metadata_id)
        if music:
            track_count = music.get("track_count")
            if track_count is not None:
                metadata_json["track_count"] = track_count
            tracks = music.get("tracks")
            if isinstance(tracks, list) and tracks:
                metadata_json["tracks"] = tracks
        color = color_values.get(metadata_id)
        if color:
            metadata_json["color"] = color

    for metadata_id, metadata_json in metadata_by_id.items():
        bind.execute(
            sa.text(
                "UPDATE item_kind_metadata SET metadata_json = CAST(:metadata_json AS JSONB) WHERE id = :id"
            ),
            {
                "id": metadata_id,
                "metadata_json": json.dumps(metadata_json) if metadata_json else None,
            },
        )

    op.drop_table("item_kind_metadata_taxonomies")
    op.drop_table("metadata_taxonomies")
    op.drop_table("item_kind_metadata_music_tracks")
    op.drop_table("item_kind_metadata_music")
    op.drop_table("item_kind_metadata_anime")
    op.drop_table("item_kind_metadata_boardgame")
    op.drop_table("item_kind_metadata_book")
    op.drop_table("item_kind_metadata_collection")
    op.drop_table("item_kind_metadata_comic")
    op.drop_table("item_kind_metadata_game")
    op.drop_table("item_kind_metadata_manga")
    op.drop_table("item_kind_metadata_movie")
    op.drop_table("item_kind_metadata_tv")


def downgrade() -> None:
    raise NotImplementedError("Downgrade for item_kind_metadata subtype removal is not supported.")
