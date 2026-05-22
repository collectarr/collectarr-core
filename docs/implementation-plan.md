# 🗺️ Collectarr Core — Implementation Plan

> Core owns the shared metadata server, provider integrations, image delivery, search, admin identity, audit logs, worker jobs, and the Admin Console.

## ✅ Done

### 🏗️ Infrastructure
- Split from monorepo into `collectarr/collectarr-core`
- CI runs Python lint/tests and Docker Compose validation
- Single squashed Alembic migration with role-based user model

### 🔌 Providers
- 9 provider integrations: GCD, ComicVine, AniList, MangaDex, OpenLibrary, BGG, MusicBrainz, IGDB, TMDb
- Search guardrails: cache, cooldown/backoff, rate limiting (Redis-backed)
- Shared normalization: accent stripping, title aliases, issue sort keys
- Smoke fixture tests for all 9 providers
- Structured comic search context (series, issue number, year)
- Provider candidates with typed comic identity fields (candidate_type, series_title, variant_name, etc.)
- Short-lived hydrated preview caching avoids repeating upstream fetch/normalize work between preview and ingest
- Preview/ingest flows preserve provider-native raw IDs while sharing hydrated provider data

### 📚 Catalog
- Series → items → editions → variants → releases → people → organizations → tags
- MangaDex volume/chapter support through metadata volumes API
- DB-backed ingest job queue with automatic worker processing

### 🛠️ Admin Console
- Provider health dashboard, ingest queue management, catalog inspector
- Duplicate candidate detection with merge/ignore actions
- User management with viewer/editor/admin roles + audit trail
- Image cache stats + purge endpoints
- Metadata proposals, cover inspection, search index history

### 🖼️ Image Pipeline
- External provider URLs as default delivery
- Optional MinIO/S3 mirroring with WebP normalization
- SHA256 dedup, LRU eviction, cache budget tracking
- Admin visibility: stats endpoint + purge endpoint + UI panel
- User-uploaded image mirroring uses content-addressed synthetic source URLs to avoid key collisions
- Canonical image asset mutations are restricted to admins
- Provider image mirroring can stay off the synchronous search hot path via cache-only reuse when assets are already mirrored

### 📄 Contracts
- OpenAPI auto-generated with tags (system, auth, metadata, admin)
- `scripts/export_openapi.py` for versioned schema snapshots

## 🔜 Next Up

### 🎯 Provider Quality
- [x] Deeper GCD + ComicVine matching: credits, story arcs, publisher imprints
- [x] Barcode/UPC → provider item resolution for all media types
- [x] Provider-specific enrichment for music (MusicBrainz releases) and games (IGDB platforms/editions)
- [x] Scheduled catalog refresh for stale provider data
- [x] Preserve provider-native raw IDs through preview/ingest normalization flows

### 🛡️ Operations
- [x] HTTPS + secrets rotation documentation
- [x] Metrics/exporters for provider health and ingest throughput
- [x] GHCR/private-registry image flow docs
- [x] Backup/restore runbook for PostgreSQL + MinIO

### 🧩 Post-MVP
- [ ] Rich duplicate/merge tooling with confidence scoring
	- Add explainable confidence factors so operators can see why two records were suggested as merge candidates (title aliases, provider IDs, barcode/UPC, release dates, creators, formats).
	- Start with operator-reviewed merge suggestions and audit trails before any automatic merge behavior.
	- Cover merge outcomes across canonical entities and provider IDs so ingest, search, and App snapshots keep stable references.
- [ ] Per-media normalization: music releases, book editions, video physical releases, game platforms
	- Expand normalization depth where providers already expose richer release structures: music labels/catalog numbers, book ISBN/edition/imprint, video format/runtime/region, and game platform/edition metadata.
	- Keep the normalized contract stable enough that App can surface new fields without provider-specific branching in UI code.
- [ ] Public deployment hardening and stricter operator roles
	- Split operational privileges more finely than viewer/editor/admin where public-hosted deployments need safer ingest, merge, and cache controls.
	- Tighten production guidance around auth defaults, CORS, rate limits, job isolation, and secrets management for internet-facing operators.
- [x] DevStack orchestration entrypoint for local full-stack development
