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

### 📄 Contracts
- OpenAPI auto-generated with tags (system, auth, metadata, admin)
- `scripts/export_openapi.py` for versioned schema snapshots

## 🔜 Next Up

### 🎯 Provider Quality
- [x] Deeper GCD + ComicVine matching: credits, story arcs, publisher imprints
- [ ] Barcode/UPC → provider item resolution for all media types
- [ ] Provider-specific enrichment for music (MusicBrainz releases) and games (IGDB platforms/editions)
- [ ] Scheduled catalog refresh for stale provider data

### 🛡️ Operations
- [ ] HTTPS + secrets rotation documentation
- [ ] Metrics/exporters for provider health and ingest throughput
- [ ] GHCR/private-registry image flow docs
- [ ] Backup/restore runbook for PostgreSQL + MinIO

### 🧩 Post-MVP
- [ ] Rich duplicate/merge tooling with confidence scoring
- [ ] Per-media normalization: music releases, book editions, video physical releases, game platforms
- [ ] Public deployment hardening and stricter operator roles
- [ ] DevStack orchestration repo for local full-stack development
