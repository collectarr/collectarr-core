# Collectarr Data Boundaries

Collectarr splits data across three stores:

- Core PostgreSQL stores shared, canonical catalog metadata only.
- App Drift stores catalog cache, owned copies, and personal library state.
- Optional `collectarr-sync` stores user-owned events for multi-device sync.

Core must not store owned copies, wishlist state, tracking progress, prices,
condition, grades, notes, personal tags, personal images, or local locations.
Provider search, credentials, source IDs, import history, and provenance also
belong to App. Core receives complete, source-neutral catalog objects.

## Core Catalog

The schema is kind-first. Music has one `music_albums` row per catalog edition
and contained `music_album_disc_titles`, `music_album_tracks`, and
`music_album_credits` rows. Tracks are ordered by album, disc number, and
position. Discs have no independent identity. Other kinds keep their typed
work, release, edition, or episode structures.

Repeated values use typed relation tables where their semantics need ordering
or identity. Common neutral relations include people, organizations, aliases,
links, and editorial tags. The generated
[schema-full.md](schema-full.md) and [schema viewer](schema.html) describe the
current SQLAlchemy schema.

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

The coordinated Music cutover replaces the old Core release-group/release/medium
graph and resets Core PostgreSQL and App Drift to their final v1 schemas.
Existing databases and backups from the old formats are incompatible. Create
empty databases and rebuild the search index from the new catalog. Core's
`create_all()` creates missing tables but does not reshape old ones; see
[deployment.md](deployment.md).
