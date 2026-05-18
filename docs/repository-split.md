# Repository Split Plan

Collectarr should split by deployable ownership boundary, not by technology
alone. The first split should use three repositories:

- `collectarr-core`
- `collectarr-sync`
- `collectarr-app`

A separate `collectarr-devstack` repository can wait until local orchestration
becomes too noisy for Core. For the first split, Core can temporarily own the
cross-service local compose files and smoke scripts because it is the service
that depends on Postgres, Redis, Meilisearch, MinIO, providers, and the worker.

## collectarr-core

Core is the shared metadata and operations server.

It owns:

- FastAPI metadata API
- canonical catalog schema and migrations
- provider plugins and provider routing
- provider search cache, rate limits, cooldown/backoff, and ingest jobs
- worker processes for indexing, provider ingest, image jobs, and stale job
  recovery
- image references, optional MinIO/S3 image cache, generated fallback assets,
  and cover inspection/replacement operations
- search indexing through Meilisearch
- admin identity, permissions, audit logs, and destructive-operation guardrails
- Core Admin Console
- production and local infrastructure docs for Core dependencies

The Core Admin Console is part of `collectarr-core`, not `collectarr-app`.
It should evolve into a Grafana-like operational frontend for the metadata
server. It is for server operators and metadata admins, not day-to-day library
browsing.

Core Admin Console responsibilities:

- server health, worker health, queue health, and storage/index status
- provider status, credentials visibility, rate-limit/cooldown state, and
  compliance labels
- ingest job queue, timeline, retry/backoff, and persistent error queue
- catalog coverage, missing provider IDs, missing covers, duplicate candidates,
  and metadata quality dashboards
- canonical item detail with provider links, editions, variants, cover status,
  image cache state, and audit history
- metadata proposal moderation and provider candidate ingest review
- admin account creation, role management, and permission audit
- destructive admin actions with preview and typed confirmation

Core must not store personal collection data such as owned items, wishlist,
grades, purchase prices, personal notes, local shelves, or reading/watch/play
progress.

Current monorepo source paths that move to Core:

- `backend/`
- Core-focused docs such as `docs/architecture.md`, `docs/schema.md`,
  `docs/image-pipeline.md`, `docs/deployment.md`
- local Core/dev orchestration scripts until a later devstack split:
  `docker-compose.yml`, `.env.example`, `scripts/`, and `tools/dev.ps1`

## collectarr-sync

Sync is the optional user-hosted personal sync service.

It owns:

- personal sync protocol
- sync storage and migrations
- device identity/pairing service endpoints
- push/pull/change APIs
- tombstones and conflict handling
- sync-specific authentication if one service is exposed to multiple users
- sync backup/restore docs

Sync stores personal sync snapshots and sync events only for the user's own
devices. It should not fetch provider metadata directly and should not become a
second metadata catalog.

Current monorepo source paths that move to Sync:

- `sync_service/`
- `docs/sync.md`
- sync-specific sections from `docs/architecture.md` and
  `docs/implementation-plan.md`

## collectarr-app

App is the user-facing Flutter client.

It owns:

- Flutter UI for local libraries
- local Drift database
- local catalog snapshots used for offline-first browsing
- owned/wishlist/personal fields
- import/export flows, including CSV/CLZ
- barcode scanning/manual fallback UX
- sync client, pairing UX, conflict review/actions, and local retry queue
- platform builds and app branding assets

The app can include admin-adjacent surfaces only when they help the user
understand their configured Core account, such as connection status or whether
their account has admin permissions. The operational admin UI belongs in Core.

Current monorepo source paths that move to App:

- `frontend/`
- app-focused docs such as `docs/import-export.md`,
  `docs/barcode-smoke-tests.md`, and app branding assets

## Contracts Between Repositories

The split needs explicit contracts so the repos can move independently without
guesswork.

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

- Core OpenAPI/generated or hand-maintained REST client
- Sync protocol schema
- media catalog fallback data for offline/dev mode

## First Split Sequence

1. Freeze `main` long enough to split from a known commit.
2. Create the GitHub organization and the three repositories.
3. Copy repository-level metadata: license, security policy, issue templates,
   pull request templates, and basic branch protection.
4. Split history with `git filter-repo` in throwaway clones so each target
   repo keeps history for its owned root files, docs, scripts, and source
   directory. `git subtree split --prefix=...` is only enough when the target
   repo should contain one directory and nothing else.

   ```powershell
   git clone . ../collectarr-core-split
   cd ../collectarr-core-split
   git filter-repo `
     --path backend/ `
     --path docs/architecture.md `
     --path docs/schema.md `
     --path docs/image-pipeline.md `
     --path docs/deployment.md `
     --path docker-compose.yml `
     --path .env.example `
     --path scripts/ `
     --path tools/dev.ps1 `
     --path LICENSE `
     --path README.md `
     --path-rename backend/:
   ```

   ```powershell
   git clone . ../collectarr-sync-split
   cd ../collectarr-sync-split
   git filter-repo `
     --path sync_service/ `
     --path docs/sync.md `
     --path LICENSE `
     --path-rename sync_service/:
   ```

   ```powershell
   git clone . ../collectarr-app-split
   cd ../collectarr-app-split
   git filter-repo `
     --path frontend/ `
     --path docs/import-export.md `
     --path docs/barcode-smoke-tests.md `
     --path docs/assets/ `
     --path LICENSE `
     --path-rename frontend/:
   ```

   If a quick directory-only split is acceptable for a throwaway first pass,
   keep branch names aligned with the target repositories:

   ```powershell
   git subtree split --prefix=backend -b split/collectarr-core
   git subtree split --prefix=sync_service -b split/collectarr-sync
   git subtree split --prefix=frontend -b split/collectarr-app
   ```

5. Rewrite repo-local README files and CI paths after the history split.
6. Rebuild CI in each repository:
   - Core: ruff, backend tests, compose config, Docker image build
   - Sync: sync tests, package build, Docker image build
   - App: Flutter analyze/test/build
7. Add cross-repo compatibility checks after the first clean split:
   - App against a pinned Core OpenAPI schema
   - App against a pinned Sync protocol schema
   - Core smoke with provider ingest and admin UI
8. Keep the old monorepo read-only or turn it into a short-lived migration
   tracker until issues and docs are moved.

## Open Decisions

- Organization name and ownership.
- Whether Core Admin Console remains a FastAPI-served static app or becomes a
  separate frontend folder inside `collectarr-core`.
- Whether local full-stack compose stays in `collectarr-core` for MVP or later
  moves to `collectarr-devstack`.
- Whether releases are versioned independently or coordinated as a compatibility
  matrix, for example Core `0.1.x`, Sync `0.1.x`, App `0.1.x`.
