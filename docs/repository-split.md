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

- canonical catalog schema and schema bootstrap
- source-neutral canonical write contracts and catalog persistence
- search, indexing, and worker processes
- image references, optional MinIO/S3 image cache, generated fallback covers,
  and cover inspection/replacement operations
- admin identity, permissions, audit logs, destructive-operation guardrails, and
  Core Admin Console
- Core deployment and operations docs

Provider search, credentials, mapping, source IDs, import history, snapshots,
and provider-specific ingest orchestration belong in `collectarr-app`. Core
receives canonical objects prepared by App and does not expose provider routes
or persist provider provenance.

`collectarr-sync` owns optional personal sync:

- sync push/pull/change APIs
- sync storage and schema bootstrap
- device identity/pairing protocol
- tombstones, conflicts, and sync backup/restore docs

`collectarr-app` owns the user-facing client:

- Flutter UI and platform builds
- local Drift database
- local catalog snapshots used for offline-first browsing
- owned/wishlist/personal fields
- provider adapters, CSV/CLZ import-export, and importer workflows
- barcode scanning/manual fallback UX
- sync client, pairing UX, conflict review/actions, and local retry queue

## Contracts Between Repositories

Core publishes:

- OpenAPI schema for metadata/admin/auth endpoints
- media catalog contract for `/api/v1/metadata/media-types`
- Music Album v1 catalog contract
- editable metadata field schema and active-kind list
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

Cross-repo orchestration now lives as a lightweight overlay on top of that stack:
`docker-compose.devstack.yml` plus `./tools/dev.ps1 start -WithSync` start Core
and `collectarr-sync` together for local full-stack development. A separate
`collectarr-devstack` repository is only needed later if we also want to pin and
publish a built App as part of the same local orchestration surface.
