"""Consolidate provider links to ExternalProviderId model.

Revision ID: 20260627_0001
Revises: 20260626_1501
Create Date: 2026-06-27 00:01:00.000000

Migration consolidates 4 ProviderLink types (ItemProviderLink, SeriesProviderLink,
VolumeProviderLink, BundleReleaseProviderLink) into the unified ExternalProviderId model.
This aligns v0 (games/boardgames) with v1 pattern used by other kinds.

Old tables are preserved for rollback safety but marked as deprecated.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260627_0001"
down_revision: str | None = "20260626_1501"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Migrate ItemProviderLink to ExternalProviderId
    op.execute(
        """
        INSERT INTO external_provider_ids (id, provider, provider_item_id, entity_type, entity_id, site_url, api_url, created_at, updated_at)
        SELECT gen_random_uuid(), provider, provider_item_id, 'item', item_id, site_url, api_url, created_at, updated_at
        FROM item_provider_links
        ON CONFLICT DO NOTHING
        """
    )

    # Migrate SeriesProviderLink to ExternalProviderId
    op.execute(
        """
        INSERT INTO external_provider_ids (id, provider, provider_item_id, entity_type, entity_id, site_url, api_url, created_at, updated_at)
        SELECT gen_random_uuid(), provider, provider_item_id, 'series', series_id, site_url, api_url, created_at, updated_at
        FROM series_provider_links
        ON CONFLICT DO NOTHING
        """
    )

    # Migrate VolumeProviderLink to ExternalProviderId
    op.execute(
        """
        INSERT INTO external_provider_ids (id, provider, provider_item_id, entity_type, entity_id, site_url, api_url, created_at, updated_at)
        SELECT gen_random_uuid(), provider, provider_item_id, 'volume', volume_id, site_url, api_url, created_at, updated_at
        FROM volume_provider_links
        ON CONFLICT DO NOTHING
        """
    )

    # Migrate BundleReleaseProviderLink to ExternalProviderId
    op.execute(
        """
        INSERT INTO external_provider_ids (id, provider, provider_item_id, entity_type, entity_id, site_url, api_url, created_at, updated_at)
        SELECT gen_random_uuid(), provider, provider_item_id, 'bundle_release', bundle_release_id, site_url, api_url, created_at, updated_at
        FROM bundle_release_provider_links
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Delete migrated ExternalProviderId records
    op.execute("DELETE FROM external_provider_ids WHERE entity_type IN ('item', 'series', 'volume', 'bundle_release')")
