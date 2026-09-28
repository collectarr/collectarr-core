# Architecture

## Domain Boundary

Core owns canonical Catalog Items and their typed contained data. One Catalog
Item represents a concrete collectible edition, version, or issue variant. It
is the only shared catalog root for all nine kinds. Tracks, episodes, credits,
components, included editions, and similar repeated values remain contained
children rather than separate Work or Release records.

Core accepts source-neutral writes prepared by the App. It does not search
providers, store provider credentials or IDs, retain provider snapshots, or run
provider import jobs. App owns Owned Copies, tracking, and personal fields.

```text
Shared catalog: CatalogItem(kind, id) -> typed contained data
Local library:  CatalogItemRef -> OwnedCopyRef 0..N
```

## Backend Layers

API routers validate requests, call focused services, and return typed DTOs.
Services own canonical validation, identifier deduplication, persistence, and
search-index decisions. Repositories own database query details.

The active SQLAlchemy model registry contains Catalog Items, normalized
identifiers, users, catalog images, audit records, and duplicate-review
records. Per-kind Work/Release ORM models and routes have been removed. A fresh
schema bootstrap therefore creates only these active tables. `create_all()`
does not remove obsolete tables from an existing database.

## Repository Boundaries

- `collectarr-core`: canonical Catalog Item API and database, source-neutral
  writes, typed contracts, search indexing, catalog images, and administration.
- `collectarr-sync`: optional sync for user-owned data and conflict handling.
- `collectarr-app`: Flutter client, local catalog cache, Owned Copies, and
  personal library state.

The coordinated v1 release uses fresh Core and App databases and rebuilds the
search index. Existing databases and backups from the previous graph need
archival handling; see [deployment.md](deployment.md).

## Personal Data

Owned Copies, wishlist entries, purchase details, condition, notes, personal
images, listening history, and personal tags stay in the App. Core does not
expose personal collection or sync endpoints. Multi-device sync belongs in
`collectarr-sync`.

## Search

PostgreSQL is the source of truth and Meilisearch is a derived index. Catalog
writes update PostgreSQL and the worker rebuilds source-neutral v1 search
documents. Search currently uses SQL text matching and needs indexed exact
identifier lookup and pagination for large catalogs. Catalog edits and
duplicate-review decisions are recorded in persistent audit logs.

## Images

Catalog Item images use the `catalog_item` entity type. Core stores external
URLs or uploaded image assets; it does not store Owned Copy images. MinIO/S3
holds manual uploads and generated assets, while the optional cache stores
processed image bytes.

## Scaling

The API is stateless. Durable state lives in PostgreSQL, Meilisearch, and
MinIO/S3. Redis carries shared ephemeral rate-limit state. API and worker
containers can scale independently.
