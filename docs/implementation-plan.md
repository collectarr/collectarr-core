# 🗺️ Collectarr Core — Implementation Plan

> Core owns the shared metadata server, provider integrations, image delivery, search, admin identity, audit logs, worker jobs, and the Admin Console.

## ✅ Done

### 🏗️ Infrastructure
- Split from monorepo into `collectarr/collectarr-core`
- CI runs Python lint/tests and Docker Compose validation
- Single squashed Alembic migration with role-based user model

### 🔌 Providers
- 10 provider integrations: GCD, ComicVine, Hardcover, AniList, MangaDex, OpenLibrary, BGG, MusicBrainz, IGDB, TMDb
- Search guardrails: cache, cooldown/backoff, rate limiting (Redis-backed)
- Shared normalization: accent stripping, title aliases, issue sort keys
- Smoke fixture tests for all 9 providers
- Structured comic search context (series, issue number, year)
- Provider candidates with typed comic identity fields (candidate_type, series_title, variant_name, etc.)
- Short-lived hydrated preview caching avoids repeating upstream fetch/normalize work between preview and ingest
- Preview/ingest flows preserve provider-native raw IDs while sharing hydrated provider data
- Ingest persistence hardening for normalized metadata (`audience_rating`, `volume_number`) and comic-only story-arc fallback semantics

### 📚 Catalog
- Historical generic projection tables were removed from the canonical schema. All canonical metadata is kind-specific.
- Bundle composition uses `bundle_release_components`.
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
- Exported contract bundle: `contracts/openapi.json`, `contracts/metadata-field-schema.json`, `contracts/active-kinds.json`, `contracts/provider-support.json`, `contracts/contract-manifest.json`
- `scripts/export_openapi.py` for versioned schema snapshots

### 🔓 API Access
- Read-only metadata endpoints (search, facets, series, seasons, volumes, bundle releases, provider search/preview) are public — no auth required
- Write endpoints are kind-specific
- Keeps App usable without login for browsing/searching metadata

## 🔜 Active Roadmap

### 🎯 Metadata Contract + Ingest Reliability
- [x] Stabilize typed-per-kind metadata storage as canonical contract
	- Typed per-kind fields now live in kind-specific canonical tables.
	- Shared genre/platform classification now uses taxonomy link tables again instead of per-kind scalar columns.
	- Keep admin drift diagnostics (`typed_*` issue keys) as the release gate.
- [x] Split metadata service seams
	- Typed reads, facets, search, providers, proposals, and legacy projection now have separate service entrypoints/helpers.
- [ ] Continue per-media normalization depth
	- Expand provider mapping where upstream data still exists for video, book/manga, and game metadata.

### 🧭 Admin UX / Operations
- [ ] Expand duplicate/merge operator workflow from confidence signals to full review queue
	- Turn confidence factors/warnings into explicit queue decisions with richer audit context.
- [ ] Continue public deployment hardening for internet-facing setups
	- Keep tightening auth defaults, CORS, rate limits, job isolation, and secrets guidance.

### 🗂️ Schema Explorer / Taxonomy Clarity
- [ ] Keep the interactive schema explorer split into navigable domains and kind views
	- Continue color-coding generic vs kind-specific areas so the table hierarchy is visually obvious.
- [ ] Consider further pagination/collapse for very dense sections
	- Add more progressive disclosure if the generated markdown or explorer still feels overloaded.

### 🧩 Scan-to-Identify Boundary
- [x] Re-evaluate whether Core needs any role in comics cover-photo recognition / scan-to-identify
	- Keep the app local-first by default; Core stays on image storage/search primitives and does not own identify flows.
