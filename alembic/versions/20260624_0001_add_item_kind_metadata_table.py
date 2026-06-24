"""Add typed item kind metadata table.

Revision ID: 20260624_0001
Revises: 20260604_0001
Create Date: 2026-06-24 11:58:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260624_0001"
down_revision: str | None = "20260604_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "item_kind_metadata",
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Enum(name="item_kind", create_type=False), nullable=False),
        sa.Column("audience_rating", sa.String(length=64), nullable=True),
        sa.Column("genres", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("platforms", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("color", sa.String(length=64), nullable=True),
        sa.Column("nr_discs", sa.Integer(), nullable=True),
        sa.Column("screen_ratio", sa.String(length=64), nullable=True),
        sa.Column("audio_tracks", sa.String(length=255), nullable=True),
        sa.Column("subtitles", sa.String(length=255), nullable=True),
        sa.Column("layers", sa.String(length=255), nullable=True),
        sa.Column("track_count", sa.Integer(), nullable=True),
        sa.Column("tracks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("nr_discs IS NULL OR nr_discs >= 0", name="ck_item_kind_metadata_nr_discs_nonnegative"),
        sa.CheckConstraint(
            "track_count IS NULL OR track_count >= 0",
            name="ck_item_kind_metadata_track_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", name="uq_item_kind_metadata_item_id"),
    )
    op.create_index("ix_item_kind_metadata_kind", "item_kind_metadata", ["kind"])
    op.create_index("ix_item_kind_metadata_audience_rating", "item_kind_metadata", ["audience_rating"])

    op.execute(
        sa.text(
            """
            WITH primary_edition AS (
                SELECT DISTINCT ON (e.item_id)
                    e.item_id,
                    e.metadata_json
                FROM editions e
                ORDER BY e.item_id, e.created_at ASC NULLS LAST, e.id ASC
            ),
            merged AS (
                SELECT
                    i.id AS item_id,
                    i.kind,
                    (COALESCE(i.metadata_json->'normalized', '{}'::jsonb) || COALESCE(pe.metadata_json->'normalized', '{}'::jsonb)) AS normalized
                FROM items i
                LEFT JOIN primary_edition pe ON pe.item_id = i.id
            ),
            extracted AS (
                SELECT
                    item_id,
                    kind,
                    NULLIF(BTRIM(normalized->>'audience_rating'), '') AS audience_rating,
                    CASE
                        WHEN jsonb_typeof(normalized->'genres') = 'array'
                        THEN ARRAY(SELECT jsonb_array_elements_text(normalized->'genres'))
                        ELSE NULL
                    END AS genres,
                    CASE
                        WHEN jsonb_typeof(normalized->'platforms') = 'array'
                        THEN ARRAY(SELECT jsonb_array_elements_text(normalized->'platforms'))
                        ELSE NULL
                    END AS platforms,
                    NULLIF(BTRIM(normalized->>'color'), '') AS color,
                    CASE
                        WHEN jsonb_typeof(normalized->'nr_discs') = 'number'
                        THEN (normalized->>'nr_discs')::integer
                        ELSE NULL
                    END AS nr_discs,
                    NULLIF(BTRIM(normalized->>'screen_ratio'), '') AS screen_ratio,
                    NULLIF(BTRIM(normalized->>'audio_tracks'), '') AS audio_tracks,
                    NULLIF(BTRIM(normalized->>'subtitles'), '') AS subtitles,
                    NULLIF(BTRIM(normalized->>'layers'), '') AS layers,
                    CASE
                        WHEN jsonb_typeof(normalized->'track_count') = 'number'
                        THEN (normalized->>'track_count')::integer
                        ELSE NULL
                    END AS track_count,
                    CASE
                        WHEN jsonb_typeof(normalized->'tracks') = 'array'
                        THEN normalized->'tracks'
                        ELSE NULL
                    END AS tracks
                FROM merged
            )
            INSERT INTO item_kind_metadata (
                item_id,
                kind,
                audience_rating,
                genres,
                platforms,
                color,
                nr_discs,
                screen_ratio,
                audio_tracks,
                subtitles,
                layers,
                track_count,
                tracks,
                id,
                created_at,
                updated_at
            )
            SELECT
                item_id,
                kind,
                audience_rating,
                genres,
                platforms,
                color,
                nr_discs,
                screen_ratio,
                audio_tracks,
                subtitles,
                layers,
                track_count,
                tracks,
                item_id,
                NOW(),
                NOW()
            FROM extracted
            WHERE audience_rating IS NOT NULL
               OR genres IS NOT NULL
               OR platforms IS NOT NULL
               OR color IS NOT NULL
               OR nr_discs IS NOT NULL
               OR screen_ratio IS NOT NULL
               OR audio_tracks IS NOT NULL
               OR subtitles IS NOT NULL
               OR layers IS NOT NULL
               OR track_count IS NOT NULL
               OR tracks IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_item_kind_metadata_audience_rating", table_name="item_kind_metadata")
    op.drop_index("ix_item_kind_metadata_kind", table_name="item_kind_metadata")
    op.drop_table("item_kind_metadata")
