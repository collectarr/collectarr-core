"""add provider ingest jobs

Revision ID: 202605140003
Revises: 202605140002
Create Date: 2026-05-14 18:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202605140003"
down_revision: str | None = "202605140002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    external_provider = postgresql.ENUM(
        "anilist",
        "bgg",
        "comicvine",
        "gcd",
        "igdb",
        "musicbrainz",
        "openlibrary",
        "tmdb",
        name="external_provider",
        create_type=False,
    )
    op.create_table(
        "provider_ingest_jobs",
        sa.Column("provider", external_provider, nullable=False),
        sa.Column("provider_item_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("item_id", sa.UUID(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_ingest_jobs_provider_item",
        "provider_ingest_jobs",
        ["provider", "provider_item_id"],
    )
    op.create_index(
        "ix_provider_ingest_jobs_status_next_run",
        "provider_ingest_jobs",
        ["status", "next_run_at"],
    )
    op.create_index(
        op.f("ix_provider_ingest_jobs_item_id"),
        "provider_ingest_jobs",
        ["item_id"],
    )
    op.create_index(
        op.f("ix_provider_ingest_jobs_next_run_at"),
        "provider_ingest_jobs",
        ["next_run_at"],
    )
    op.create_index(
        op.f("ix_provider_ingest_jobs_provider"),
        "provider_ingest_jobs",
        ["provider"],
    )
    op.create_index(
        op.f("ix_provider_ingest_jobs_provider_item_id"),
        "provider_ingest_jobs",
        ["provider_item_id"],
    )
    op.create_index(
        op.f("ix_provider_ingest_jobs_status"),
        "provider_ingest_jobs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_provider_ingest_jobs_status"), table_name="provider_ingest_jobs")
    op.drop_index(
        op.f("ix_provider_ingest_jobs_provider_item_id"),
        table_name="provider_ingest_jobs",
    )
    op.drop_index(op.f("ix_provider_ingest_jobs_provider"), table_name="provider_ingest_jobs")
    op.drop_index(
        op.f("ix_provider_ingest_jobs_next_run_at"),
        table_name="provider_ingest_jobs",
    )
    op.drop_index(op.f("ix_provider_ingest_jobs_item_id"), table_name="provider_ingest_jobs")
    op.drop_index("ix_provider_ingest_jobs_status_next_run", table_name="provider_ingest_jobs")
    op.drop_index("ix_provider_ingest_jobs_provider_item", table_name="provider_ingest_jobs")
    op.drop_table("provider_ingest_jobs")
