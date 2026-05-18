# Collectarr Core Implementation Plan

Core owns the shared metadata/catalog server, provider integrations, image
delivery, search, admin identity, audit logs, worker jobs, and the Core Admin
Console. It must not store personal library data.

## Done

- Split from the original monorepo into `collectarr/collectarr-core`.
- CI runs Python lint/tests and Docker Compose validation.
- Provider abstraction exists for GCD, ComicVine, AniList, OpenLibrary, BGG,
  MusicBrainz, IGDB, and TMDb.
- Provider search guardrails exist: cache, cooldown/backoff, and rate limiting,
  with Redis support for shared state.
- DB-backed provider ingest jobs, retry status, and admin queue APIs exist.
- Canonical catalog supports series/items/editions/variants enough for comics
  MVP and physical video formats.
- Core Admin Console has the first operator surfaces for providers, ingest,
  metadata proposals, catalog details, cover inspection, and audit history.
- Image handling supports external provider URLs, generated fallbacks, optional
  MinIO/S3 mirroring, and cache accounting.
- Provider search endpoints accept structured comic context (`series`,
  `issue_number`, `year`) so clients can ask for Add Series/Add Issue flows
  without encoding provider-specific query semantics.
- Provider search results expose optional typed comic identity fields
  (`candidate_type`, `series_title`, `issue_number`, `volume_start_year`,
  `variant_name`, `is_variant`) for provider-backed issue/variant grouping.

## MVP Priorities

1. Provider-backed catalog quality
   - Stabilize comics search for GCD + ComicVine: title normalization, issue
     number matching, series aliases, variants, publisher/release dates,
     credits/story arcs, barcode/UPC, and cover fallback.
   - Keep non-comics provider search safe and honest: show unavailable or
     unconfigured providers, avoid parallel fallback by default, and cache
     provider responses by provider/kind/query.
   - Add provider-specific smoke fixtures for manga/anime/books/games/video/
     board games/music as credentials allow.

2. Core Admin Console
   - Add admin account creation and role/permission management.
   - Add catalog coverage dashboards: missing provider IDs, missing covers,
     duplicate candidates, stale ingest jobs, provider failure trends.
   - Make canonical item detail more useful: provider links, editions,
     variants, cover status, image cache status, proposals, audit history.
   - Keep destructive actions guarded with preview plus typed confirmation for
     merge/delete-like operations.

3. Image pipeline
   - Keep external provider URLs as the default delivery path.
   - Make optional MinIO/S3 mirroring explicit per provider and policy.
   - Track cache budget, LRU eviction, failures, and source URL health in admin.
   - Ensure generated fallback covers are deterministic and clearly labeled.

4. Contracts for other repos
   - Publish OpenAPI artifacts or pinned schema snapshots for App consumption.
   - Version `/metadata/media-types`, provider status, and catalog snapshot
     shapes.
   - Document breaking API changes with migration notes.

5. Deployment and operations
   - Keep `docker-compose.yml` Core-only.
   - Document GHCR/private-registry image flow for environments where Docker
     Hub is blocked.
   - Decide when local full-stack orchestration should move to a future
     `collectarr-devstack` repository.

## Post-MVP

- Rich duplicate/merge tooling with confidence scoring.
- Provider-specific enrichment workers and scheduled catalog refreshes.
- More complete per-media normalization: music releases, book editions, video
  physical releases, game platforms/editions, anime seasons.
- Public/private deployment hardening: HTTPS, secrets rotation, backup docs,
  metrics/exporters, and stricter operator roles.
