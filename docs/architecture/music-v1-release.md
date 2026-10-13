# Music v1 release baseline

The existing Music contract is relabelled v1 without restoring an older schema or API. Edition metadata, artist credits and album credits remain at the root. Physical and recording metadata, disc credits and tracks remain on stable-ID discs. Partial dates, optional contributor IDs and instrument lists retain their current strict wire shape.

Only Music is registered in the released catalog, search/navigation configuration and generated contract bundle. Other kind modules remain unreleased source; their catalog tables are not created by release migrations.

`app.db.schema_migrations` owns the baseline and future ordered migrations. A fresh database receives the current Music/shared tables and migration 1. Existing unversioned or unsupported databases are rejected without reset or inference. Later changes and new kinds require explicit, data-preserving migrations.

Core owns canonical metadata; personal library copies, loans, listening state and custom values belong to App/Sync. Changes to contract sources must regenerate the Core bundle and update the entire App pin together.

The release branch is under verification. Preparing baseline 1 does not publish a release or change existing tags and development databases.
