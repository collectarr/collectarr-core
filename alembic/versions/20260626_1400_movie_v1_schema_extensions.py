"""Add missing fields to Movie v1 schema for UI completeness.

Revision ID: 20260626_1400
Revises: 20260626_1300
Create Date: 2026-06-26 19:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260626_1400"
down_revision = "20260626_1300"
branch_labels = None
depends_on = None


def upgrade():
    # movie_works: add subtitle, age_rating, audience_rating
    op.add_column(
        "movie_works",
        sa.Column("subtitle", sa.String(500), nullable=True),
    )
    op.add_column(
        "movie_works",
        sa.Column("age_rating", sa.String(20), nullable=True),
    )
    op.add_column(
        "movie_works",
        sa.Column("audience_rating", sa.String(50), nullable=True),
    )

    # movie_releases: add distributor
    op.add_column(
        "movie_releases",
        sa.Column("distributor", sa.String(255), nullable=True),
    )

    # movie_release_media: add video specs
    op.add_column(
        "movie_release_media",
        sa.Column("num_discs", sa.Integer, nullable=True),
    )
    op.add_column(
        "movie_release_media",
        sa.Column("color", sa.String(50), nullable=True),
    )
    op.add_column(
        "movie_release_media",
        sa.Column("screen_ratio", sa.String(50), nullable=True),
    )
    op.add_column(
        "movie_release_media",
        sa.Column("audio_tracks", sa.String(500), nullable=True),
    )
    op.add_column(
        "movie_release_media",
        sa.Column("subtitles", sa.String(500), nullable=True),
    )
    op.add_column(
        "movie_release_media",
        sa.Column("layers", sa.String(50), nullable=True),
    )


def downgrade():
    # Reverse order: remove columns we added
    op.drop_column("movie_release_media", "layers")
    op.drop_column("movie_release_media", "subtitles")
    op.drop_column("movie_release_media", "audio_tracks")
    op.drop_column("movie_release_media", "screen_ratio")
    op.drop_column("movie_release_media", "color")
    op.drop_column("movie_release_media", "num_discs")

    op.drop_column("movie_releases", "distributor")

    op.drop_column("movie_works", "audience_rating")
    op.drop_column("movie_works", "age_rating")
    op.drop_column("movie_works", "subtitle")
