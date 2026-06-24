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
- Ingest persistence hardening for normalized metadata (`audience_rating`, `volume_number`) and comic-only story-arc fallback semantics

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

### 🔓 API Access
- Read-only metadata endpoints (search, facets, series, seasons, volumes, bundle releases, provider search/preview) are public — no auth required
- Write endpoints (create edition, admin mutations) remain auth-protected
- Keeps App usable without login for browsing/searching metadata

## 🔜 Active Roadmap

### 🎯 Metadata Contract + Ingest Reliability
- [ ] Stabilize typed-per-kind metadata storage as canonical contract
	- Keep `item_kind_metadata` parent + per-kind child tables as the only authority for typed normalized fields.
	- Keep admin drift diagnostics (`typed_*` issue keys) as a release gate before ingest/correction changes.
- [ ] Continue per-media normalization depth
	- Expand provider mapping where upstream data exists (video specs, richer book/manga edition signals, game release metadata).
	- Fractional `volume_number` support is now enabled end-to-end (`float` contract + ingest + preview) so providers like Hardcover can preserve positions like `1.5`.

### 🧭 Admin UX / Operations
- [ ] Expand duplicate/merge operator workflow from confidence signals to full review queue
	- Confidence factors + warnings are now exposed by API; next step is explicit queue decisions with richer audit context.
- [ ] Continue public deployment hardening for internet-facing setups
	- Admin read APIs now enforce authenticated editor/admin access in public envs by default.
	- Continue tightening production guidance for auth defaults, CORS, rate limits, job isolation, and secrets management.

### 🧩 Scan-to-Identify Boundary
- [ ] Re-evaluate whether Core needs any role in comics cover-photo recognition / scan-to-identify
	- Keep App as local-first default (import, review/crop/rotate, on-device OCR, safe fallback).
	- Only add a Core-side ranking endpoint if measured device accuracy/latency proves local reranking insufficient.
	- Preserve no-auto-ingest behavior for low-confidence matches.
