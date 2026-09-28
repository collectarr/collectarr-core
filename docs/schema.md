# Collectarr Data Boundaries

Collectarr splits data across three stores:

- Core PostgreSQL stores shared, canonical catalog metadata only.
- App Drift stores catalog cache, owned copies, and personal library state.
- Optional `collectarr-sync` stores user-owned events for multi-device sync.

Core must not store owned copies, wishlist state, tracking progress, prices,
condition, grades, notes, personal tags, personal images, or local locations.
Provider search, credentials, source IDs, import history, and provenance are
excluded from both Core and the target App. Core receives complete,
source-neutral Catalog Items.

## Core Catalog

The v1 schema uses one `catalog_items` row for each concrete collectible
edition, version, or release. Typed details and repeated contents are contained
in that item. Music tracks retain album, disc number, and position; discs have
no independent identity. Catalog Items do not require a Work/Release graph.

App-owned state is stored outside Core. The generated
[schema-full.md](schema-full.md) and [schema viewer](schema.html) describe the
current SQLAlchemy schema. Refresh them with
`python scripts/export_schema_site.py` after model changes.

## App Local Data

Every distinguishable physical copy has its own `OwnedCopyV1` record. A copy
references its canonical catalog target and holds its own status, location,
condition, owner, purchase/value fields, rating, notes, tags, and personal
images. Listening and tracking activity is App data and may reference the
canonical target and a specific owned copy.

## Sync

`collectarr-sync` stores only user-owned event data: current personal entity
state, an append-only change log, device IDs, and client timestamps. It is
separate from the canonical catalog API.

## Fresh v1 Reset

The coordinated release starts Core PostgreSQL and App Drift from their final
v1 schemas. Core's active model registry no longer defines the old Work/Release
graphs, but `create_all()` leaves old tables in an existing database.
Existing databases and backups from the old formats are incompatible. Create
empty databases and rebuild the search index from the new catalog. Core's
`create_all()` creates missing tables but does not reshape old ones; see
[deployment.md](deployment.md).
