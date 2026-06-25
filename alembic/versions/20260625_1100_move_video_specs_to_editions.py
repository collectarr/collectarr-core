"""Move video physical specs from item_kind_metadata to editions.

Revision ID: 20260625_1100
Revises: 20260625_1000
Create Date: 2026-06-25 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_1100"
down_revision: str | None = "20260625_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("editions", sa.Column("nr_discs", sa.Integer(), nullable=True))
    op.add_column("editions", sa.Column("screen_ratio", sa.String(length=64), nullable=True))
    op.add_column("editions", sa.Column("audio_tracks", sa.String(length=255), nullable=True))
    op.add_column("editions", sa.Column("subtitles", sa.String(length=255), nullable=True))
    op.add_column("editions", sa.Column("layers", sa.String(length=255), nullable=True))
    op.create_check_constraint(
        "ck_editions_nr_discs_nonnegative",
        "editions",
        "nr_discs IS NULL OR nr_discs >= 0",
    )
    op.execute(
        """
        UPDATE editions AS e
        SET
            nr_discs = COALESCE(a.nr_discs, m.nr_discs, t.nr_discs),
            screen_ratio = COALESCE(a.screen_ratio, m.screen_ratio, t.screen_ratio),
            audio_tracks = COALESCE(a.audio_tracks, m.audio_tracks, t.audio_tracks),
            subtitles = COALESCE(a.subtitles, m.subtitles, t.subtitles),
            layers = COALESCE(a.layers, m.layers, t.layers)
        FROM item_kind_metadata AS ikm
        LEFT JOIN item_kind_metadata_anime AS a ON a.id = ikm.id
        LEFT JOIN item_kind_metadata_movie AS m ON m.id = ikm.id
        LEFT JOIN item_kind_metadata_tv AS t ON t.id = ikm.id
        WHERE e.item_id = ikm.item_id
          AND ikm.kind IN ('anime', 'movie', 'tv')
          AND (
              COALESCE(a.nr_discs, m.nr_discs, t.nr_discs) IS NOT NULL OR
              COALESCE(a.screen_ratio, m.screen_ratio, t.screen_ratio) IS NOT NULL OR
              COALESCE(a.audio_tracks, m.audio_tracks, t.audio_tracks) IS NOT NULL OR
              COALESCE(a.subtitles, m.subtitles, t.subtitles) IS NOT NULL OR
              COALESCE(a.layers, m.layers, t.layers) IS NOT NULL
          )
        """
    )
    op.drop_constraint(
        "ck_item_kind_metadata_anime_nr_discs_nonnegative",
        "item_kind_metadata_anime",
        type_="check",
    )
    op.drop_constraint(
        "ck_item_kind_metadata_movie_nr_discs_nonnegative",
        "item_kind_metadata_movie",
        type_="check",
    )
    op.drop_constraint(
        "ck_item_kind_metadata_tv_nr_discs_nonnegative",
        "item_kind_metadata_tv",
        type_="check",
    )
    for table_name in (
        "item_kind_metadata_anime",
        "item_kind_metadata_movie",
        "item_kind_metadata_tv",
    ):
        op.drop_column(table_name, "nr_discs")
        op.drop_column(table_name, "screen_ratio")
        op.drop_column(table_name, "audio_tracks")
        op.drop_column(table_name, "subtitles")
        op.drop_column(table_name, "layers")


def downgrade() -> None:
    for table_name in (
        "item_kind_metadata_anime",
        "item_kind_metadata_movie",
        "item_kind_metadata_tv",
    ):
        op.add_column(table_name, sa.Column("nr_discs", sa.Integer(), nullable=True))
        op.add_column(table_name, sa.Column("screen_ratio", sa.String(length=64), nullable=True))
        op.add_column(table_name, sa.Column("audio_tracks", sa.String(length=255), nullable=True))
        op.add_column(table_name, sa.Column("subtitles", sa.String(length=255), nullable=True))
        op.add_column(table_name, sa.Column("layers", sa.String(length=255), nullable=True))
    op.create_check_constraint(
        "ck_item_kind_metadata_anime_nr_discs_nonnegative",
        "item_kind_metadata_anime",
        "nr_discs IS NULL OR nr_discs >= 0",
    )
    op.create_check_constraint(
        "ck_item_kind_metadata_movie_nr_discs_nonnegative",
        "item_kind_metadata_movie",
        "nr_discs IS NULL OR nr_discs >= 0",
    )
    op.create_check_constraint(
        "ck_item_kind_metadata_tv_nr_discs_nonnegative",
        "item_kind_metadata_tv",
        "nr_discs IS NULL OR nr_discs >= 0",
    )
    op.execute(
        """
        WITH first_edition AS (
            SELECT DISTINCT ON (item_id)
                item_id,
                nr_discs,
                screen_ratio,
                audio_tracks,
                subtitles,
                layers
            FROM editions
            ORDER BY item_id, release_date DESC NULLS LAST, created_at ASC, id ASC
        )
        UPDATE item_kind_metadata_anime AS km
        SET
            nr_discs = fe.nr_discs,
            screen_ratio = fe.screen_ratio,
            audio_tracks = fe.audio_tracks,
            subtitles = fe.subtitles,
            layers = fe.layers
        FROM item_kind_metadata AS ikm
        JOIN first_edition AS fe ON fe.item_id = ikm.item_id
        WHERE km.id = ikm.id
          AND ikm.kind = 'anime'
        """
    )
    op.execute(
        """
        WITH first_edition AS (
            SELECT DISTINCT ON (item_id)
                item_id,
                nr_discs,
                screen_ratio,
                audio_tracks,
                subtitles,
                layers
            FROM editions
            ORDER BY item_id, release_date DESC NULLS LAST, created_at ASC, id ASC
        )
        UPDATE item_kind_metadata_movie AS km
        SET
            nr_discs = fe.nr_discs,
            screen_ratio = fe.screen_ratio,
            audio_tracks = fe.audio_tracks,
            subtitles = fe.subtitles,
            layers = fe.layers
        FROM item_kind_metadata AS ikm
        JOIN first_edition AS fe ON fe.item_id = ikm.item_id
        WHERE km.id = ikm.id
          AND ikm.kind = 'movie'
        """
    )
    op.execute(
        """
        WITH first_edition AS (
            SELECT DISTINCT ON (item_id)
                item_id,
                nr_discs,
                screen_ratio,
                audio_tracks,
                subtitles,
                layers
            FROM editions
            ORDER BY item_id, release_date DESC NULLS LAST, created_at ASC, id ASC
        )
        UPDATE item_kind_metadata_tv AS km
        SET
            nr_discs = fe.nr_discs,
            screen_ratio = fe.screen_ratio,
            audio_tracks = fe.audio_tracks,
            subtitles = fe.subtitles,
            layers = fe.layers
        FROM item_kind_metadata AS ikm
        JOIN first_edition AS fe ON fe.item_id = ikm.item_id
        WHERE km.id = ikm.id
          AND ikm.kind = 'tv'
        """
    )
    op.drop_constraint("ck_editions_nr_discs_nonnegative", "editions", type_="check")
    op.drop_column("editions", "layers")
    op.drop_column("editions", "subtitles")
    op.drop_column("editions", "audio_tracks")
    op.drop_column("editions", "screen_ratio")
    op.drop_column("editions", "nr_discs")
