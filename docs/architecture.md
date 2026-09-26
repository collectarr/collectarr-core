# Architecture

> **Coordinated all-kind Catalog Item v1 cutover in progress.** The current
> typed Work/Release graphs are transitional. The target and reset gate are
> documented in [Catalog Item v1 cutover](catalog-item-v1-cutover.md).

## Domain Boundary

Core stores shared catalog metadata. The app owns provider search, credentials,
rate limits, response mapping, source identifiers, import history, provenance,
owned copies, tracking, and other personal data. Core receives complete,
source-neutral catalog objects and validates, deduplicates, persists, and indexes
them.

The target is one Catalog Item per concrete collectible edition/version/release
for every kind, with zero or more App-owned copies. Music already has a Core
Album API slice with contained disc titles and ordered tracks; the other kinds
and App persistence have not completed the all-kind cutover.

```text
Shared catalog: CatalogItem(kind, id) -> typed contained data
Local library:  CatalogItemRef -> OwnedCopyRef 0..N
```

## Backend Layers

API routers validate HTTP payloads, call services, and return typed DTOs.
Services own canonical catalog rules and search-index decisions. Repositories
own database query details.

Core has no provider adapter, provider registry, provider search or ingest route,
provider ID table, raw provider snapshot, or provider import job. Provider-native
data is mapped in `collectarr-app` before it reaches a Core catalog write.

## Repository Boundaries

- `collectarr-core`: canonical catalog API and database, source-neutral writes,
  typed metadata contracts, search indexing, image storage, catalog
  administration, and audit logs.
- `collectarr-sync`: optional personal sync API, device pairing, conflict
  handling, tombstones, and sync storage.
- `collectarr-app`: Flutter client, local Drift database, providers, import and
  export workflows, barcode UX, owned copies, and personal library state.

The coordinated all-kind v1 cutover requires empty Core PostgreSQL and App
Drift databases. Existing databases and backups from the previous graph are
incompatible with the final v1 baseline. Core's `create_all()` creates missing
tables; it does not reshape or remove old tables. See [deployment.md](deployment.md).

## Local Personal Data

Owned copies, wishlist entries, purchase dates, prices, grades, conditions,
notes, listening history, and personal tags stay in the App. The central
metadata backend does not expose `/collection` or `/sync` endpoints.

Multi-device sync belongs in the separate `collectarr-sync` service. Its
protocol owns client-generated UUIDs, device identity, conflict policy, and
tombstones.

## Search

PostgreSQL is the source of truth. Meilisearch is a derived index. Catalog writes
update PostgreSQL and enqueue or request best-effort indexing. Workers rebuild
derived search documents periodically, and API search can fall back to
PostgreSQL if Meilisearch is unavailable or empty. Catalog corrections,
duplicate actions, and proposal decisions are recorded in persistent audit logs.

## Storage

Images are represented by source-neutral URLs or stored asset references.
MinIO/S3 stores manual uploads and generated assets; the optional cache stores
processed image bytes without provider identity. Local MinIO can be configured
with a public read bucket policy through `S3_MANAGE_PUBLIC_READ_POLICY`.

## Scaling

The API is stateless. Durable state lives in PostgreSQL, Meilisearch, and MinIO.
Redis carries shared ephemeral state such as rate-limit windows. If Redis is
unavailable in local development, Core falls back to process-local state. API
and worker containers can scale independently.
