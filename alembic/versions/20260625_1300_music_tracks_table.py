"""Move music tracks from JSONB column to dedicated table.

Revision ID: 20260625_1300
Revises: 20260625_1200
Create Date: 2026-06-25 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260625_1300"
down_revision: str | None = "20260625_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_kind_metadata_music_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("item_kind_metadata_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("artist", sa.String(length=255), nullable=True),
        sa.Column("disc_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_kind_metadata_id"],
            ["item_kind_metadata_music.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_item_kind_metadata_music_tracks_duration_nonnegative",
        ),
        sa.CheckConstraint(
            "disc_number IS NULL OR disc_number >= 0",
            name="ck_item_kind_metadata_music_tracks_disc_nonnegative",
        ),
        sa.CheckConstraint(
            "position IS NULL OR position >= 0",
            name="ck_item_kind_metadata_music_tracks_position_nonnegative",
        ),
    )
    op.create_index(
        "ix_item_kind_metadata_music_tracks_owner",
        "item_kind_metadata_music_tracks",
        ["item_kind_metadata_id"],
        unique=False,
    )
    op.create_index(
        "ix_item_kind_metadata_music_tracks_sequence",
        "item_kind_metadata_music_tracks",
        ["item_kind_metadata_id", "disc_number", "position"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO item_kind_metadata_music_tracks (
            id,
            item_kind_metadata_id,
            title,
            position,
            duration_seconds,
            artist,
            disc_number,
            created_at,
            updated_at
        )
        SELECT
            (
                substr(md5(m.id::text || ':' || row.value::text), 1, 8) || '-' ||
                substr(md5(m.id::text || ':' || row.value::text), 9, 4) || '-' ||
                substr(md5(m.id::text || ':' || row.value::text), 13, 4) || '-' ||
                substr(md5(m.id::text || ':' || row.value::text), 17, 4) || '-' ||
                substr(md5(m.id::text || ':' || row.value::text), 21, 12)
            )::uuid,
            m.id,
            row.value->>'title',
            CASE WHEN (row.value->>'position') ~ '^[0-9]+$' THEN (row.value->>'position')::int ELSE NULL END,
            CASE WHEN (row.value->>'duration_seconds') ~ '^[0-9]+$' THEN (row.value->>'duration_seconds')::int ELSE NULL END,
            NULLIF(BTRIM(row.value->>'artist'), ''),
            CASE WHEN (row.value->>'disc_number') ~ '^[0-9]+$' THEN (row.value->>'disc_number')::int ELSE NULL END,
            now(),
            now()
        FROM item_kind_metadata_music AS m
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(m.tracks, '[]'::jsonb)) AS row(value)
        WHERE jsonb_typeof(COALESCE(m.tracks, '[]'::jsonb)) = 'array'
          AND NULLIF(BTRIM(row.value->>'title'), '') IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE item_kind_metadata_music AS m
        SET track_count = counts.cnt
        FROM (
            SELECT item_kind_metadata_id, count(*)::int AS cnt
            FROM item_kind_metadata_music_tracks
            GROUP BY item_kind_metadata_id
        ) AS counts
        WHERE m.id = counts.item_kind_metadata_id
        """
    )
    op.drop_column("item_kind_metadata_music", "tracks")


def downgrade() -> None:
    op.add_column(
        "item_kind_metadata_music",
        sa.Column("tracks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        """
        UPDATE item_kind_metadata_music AS m
        SET tracks = payload.tracks
        FROM (
            SELECT
                t.item_kind_metadata_id,
                jsonb_agg(
                    jsonb_build_object(
                        'position', t.position,
                        'title', t.title,
                        'duration_seconds', t.duration_seconds,
                        'artist', t.artist,
                        'disc_number', t.disc_number
                    )
                    ORDER BY t.disc_number NULLS LAST, t.position NULLS LAST, t.created_at, t.id
                ) AS tracks
            FROM item_kind_metadata_music_tracks AS t
            GROUP BY t.item_kind_metadata_id
        ) AS payload
        WHERE m.id = payload.item_kind_metadata_id
        """
    )
    op.drop_index(
        "ix_item_kind_metadata_music_tracks_sequence",
        table_name="item_kind_metadata_music_tracks",
    )
    op.drop_index(
        "ix_item_kind_metadata_music_tracks_owner",
        table_name="item_kind_metadata_music_tracks",
    )
    op.drop_table("item_kind_metadata_music_tracks")
