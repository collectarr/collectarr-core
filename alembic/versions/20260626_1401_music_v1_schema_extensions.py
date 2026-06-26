"""Add missing fields to Music v1 schema for UI completeness.

Revision ID: 20260626_1401
Revises: 20260626_1400
Create Date: 2026-06-26 19:50:30.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260626_1401"
down_revision = "20260626_1400"
branch_labels = None
depends_on = None


def upgrade():
    # music_releases: add catalog_number, release_status, studio, recording_date, extras, subtitle
    op.add_column(
        "music_releases",
        sa.Column("catalog_number", sa.String(100), nullable=True),
    )
    op.add_column(
        "music_releases",
        sa.Column("release_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "music_releases",
        sa.Column("studio", sa.String(255), nullable=True),
    )
    op.add_column(
        "music_releases",
        sa.Column("recording_date", sa.Date, nullable=True),
    )
    op.add_column(
        "music_releases",
        sa.Column("extras", sa.Text, nullable=True),
    )
    op.add_column(
        "music_releases",
        sa.Column("subtitle", sa.String(500), nullable=True),
    )

    # music_media: add packaging, media_condition, sound_type, vinyl specs
    op.add_column(
        "music_media",
        sa.Column("packaging", sa.String(100), nullable=True),
    )
    op.add_column(
        "music_media",
        sa.Column("media_condition", sa.String(100), nullable=True),
    )
    op.add_column(
        "music_media",
        sa.Column("sound_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "music_media",
        sa.Column("vinyl_color", sa.String(100), nullable=True),
    )
    op.add_column(
        "music_media",
        sa.Column("vinyl_weight", sa.String(100), nullable=True),
    )
    op.add_column(
        "music_media",
        sa.Column("rpm", sa.Integer, nullable=True),
    )
    op.add_column(
        "music_media",
        sa.Column("spars", sa.String(50), nullable=True),
    )

    # music_tracks: add instrument, composition
    op.add_column(
        "music_tracks",
        sa.Column("instrument", sa.String(100), nullable=True),
    )
    op.add_column(
        "music_tracks",
        sa.Column("composition", sa.String(255), nullable=True),
    )


def downgrade():
    # Reverse order
    op.drop_column("music_tracks", "composition")
    op.drop_column("music_tracks", "instrument")

    op.drop_column("music_media", "spars")
    op.drop_column("music_media", "rpm")
    op.drop_column("music_media", "vinyl_weight")
    op.drop_column("music_media", "vinyl_color")
    op.drop_column("music_media", "sound_type")
    op.drop_column("music_media", "media_condition")
    op.drop_column("music_media", "packaging")

    op.drop_column("music_releases", "subtitle")
    op.drop_column("music_releases", "extras")
    op.drop_column("music_releases", "recording_date")
    op.drop_column("music_releases", "studio")
    op.drop_column("music_releases", "release_status")
    op.drop_column("music_releases", "catalog_number")
