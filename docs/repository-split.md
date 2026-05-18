# Repository Split Status

Collectarr has been split from the original `saitatter/collectarr` monorepo into
three active repositories under the `collectarr` GitHub organization:

- [collectarr-core](https://github.com/collectarr/collectarr-core)
- [collectarr-sync](https://github.com/collectarr/collectarr-sync)
- [collectarr-app](https://github.com/collectarr/collectarr-app)

The old monorepo is archived and kept only for history, old pull requests, and
traceability.

## Ownership Boundaries

`collectarr-core` owns shared metadata and operations:

- canonical catalog schema and migrations
- provider integrations and provider routing
- search, indexing, provider ingest jobs, and worker processes
- image references, optional MinIO/S3 image cache, generated fallback covers,
  and cover inspection/replacement operations
- admin identity, permissions, audit logs, destructive-operation guardrails, and
  Core Admin Console
- Core deployment and operations docs

`collectarr-sync` owns optional personal sync:

- sync push/pull/change APIs
- sync storage and migrations
- device identity/pairing protocol
- tombstones, conflicts, and sync backup/restore docs

`collectarr-app` owns the user-facing client:

- Flutter UI and platform builds
- local Drift database
- local catalog snapshots used for offline-first browsing
- owned/wishlist/personal fields
- CSV/CLZ import-export
- barcode scanning/manual fallback UX
- sync client, pairing UX, conflict review/actions, and local retry queue

## Contracts Between Repositories

Core publishes:

- OpenAPI schema for metadata/admin/auth endpoints
- media catalog contract for `/metadata/media-types`
- provider status/capability schema
- canonical catalog snapshot schema used by the app
- versioned compatibility notes for API changes

Sync publishes:

- sync push/pull/change schema
- conflict payload schema
- pairing payload schema
- sync protocol version

App consumes:

- Core metadata/admin/auth APIs
- Sync protocol schema
- media catalog fallback data for offline/dev mode

## Future Devstack Decision

For MVP, Core keeps its own local Docker Compose stack because it owns the
services it depends on: Postgres, Redis, Meilisearch, MinIO, API, and worker.

A separate `collectarr-devstack` repository should be created only when local
cross-repo orchestration becomes worth maintaining separately, for example when
we want one command to start Core, Sync, and a built App against pinned versions.
