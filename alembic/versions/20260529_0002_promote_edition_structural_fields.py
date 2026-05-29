"""Promote Edition structural fields out of metadata_json.

Revision ID: 20260529_0002
Revises: 20260529_0001
Create Date: 2026-05-29 00:00:02
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260529_0002"
down_revision: str | None = "20260529_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE editions ADD COLUMN IF NOT EXISTS imprint VARCHAR(255)")
    op.execute("ALTER TABLE editions ADD COLUMN IF NOT EXISTS subtitle VARCHAR(255)")
    op.execute("ALTER TABLE editions ADD COLUMN IF NOT EXISTS series_group VARCHAR(255)")
    op.execute("ALTER TABLE editions ADD COLUMN IF NOT EXISTS age_rating VARCHAR(64)")
    op.execute("ALTER TABLE editions ADD COLUMN IF NOT EXISTS catalog_number VARCHAR(100)")
    op.execute("ALTER TABLE editions ADD COLUMN IF NOT EXISTS release_status VARCHAR(64)")

    op.execute(
        """
        UPDATE editions
        SET
            imprint = COALESCE(imprint, metadata_json -> 'normalized' ->> 'imprint'),
            subtitle = COALESCE(subtitle, metadata_json -> 'normalized' ->> 'subtitle'),
            series_group = COALESCE(series_group, metadata_json -> 'normalized' ->> 'series_group'),
            age_rating = COALESCE(age_rating, metadata_json -> 'normalized' ->> 'age_rating'),
            catalog_number = COALESCE(catalog_number, metadata_json -> 'normalized' ->> 'catalog_number'),
            release_status = COALESCE(release_status, metadata_json -> 'normalized' ->> 'release_status'),
            region = COALESCE(region, metadata_json -> 'normalized' ->> 'country'),
            language = COALESCE(language, metadata_json -> 'normalized' ->> 'language')
        WHERE metadata_json IS NOT NULL
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_editions_imprint ON editions (imprint)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_editions_series_group ON editions (series_group)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_editions_age_rating ON editions (age_rating)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_editions_catalog_number ON editions (catalog_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_editions_release_status ON editions (release_status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_editions_release_status")
    op.execute("DROP INDEX IF EXISTS ix_editions_catalog_number")
    op.execute("DROP INDEX IF EXISTS ix_editions_age_rating")
    op.execute("DROP INDEX IF EXISTS ix_editions_series_group")
    op.execute("DROP INDEX IF EXISTS ix_editions_imprint")

    op.execute("ALTER TABLE editions DROP COLUMN IF EXISTS release_status")
    op.execute("ALTER TABLE editions DROP COLUMN IF EXISTS catalog_number")
    op.execute("ALTER TABLE editions DROP COLUMN IF EXISTS age_rating")
    op.execute("ALTER TABLE editions DROP COLUMN IF EXISTS series_group")
    op.execute("ALTER TABLE editions DROP COLUMN IF EXISTS subtitle")
    op.execute("ALTER TABLE editions DROP COLUMN IF EXISTS imprint")