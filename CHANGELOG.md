# Changelog

## Unreleased

### Features
- Games, Hardware and Toys have independent catalog tables, strict contracts, search, proposal and correction routes, added via ordered migration 2.
- Derive automatic sort titles for Music items when not explicitly entered.
- Title every field and contained list in the Catalog Item schema.

### Docs
- Align agent contributing rules and token efficiency guidance with Collectarr standards.

### CI & Build
- Bump actions/upload-artifact from 4 to 7.

## 1.0.0 - 2026-10-13

The stable Music-only catalog baseline for Collectarr, with strict version-1 contracts and the current Music payload shapes preserved.

### Features
- Canonical Music catalog items with contained discs and tracks, album/disc credits and track compositions.
- Disc-specific recording dates, recording locations, live/studio state, SPARS codes and physical/technical metadata.
- Partial dates, optional contributor references and multi-instrument credits.
- Music search, barcode lookup, catalog images, vocabularies, correction proposals and catalog administration.
- Canonical writing and catalog identity checks through the unified catalog-item API.

### Fixes
- Hardened canonical field ownership, typed container validation and duplicate-identity handling.
- Removed obsolete metadata routes and stale provider/runtime paths from the public catalog stack.
- Declared required SQLAlchemy async dependencies and corrected release changelog/container-context configuration.

### Refactors
- Completed the strict typed catalog cutover and removed the old catalog graph, correction, metadata-read and seed paths.
- Kept canonical catalog ownership in Core, separate from personal library synchronization.
- Limited the released API and fresh database baseline to Music; other kinds remain unreleased.
- Removed automatic PostgreSQL cleanup from pure tests and gave authentication/catalog fixtures explicit ownership.

### CI & Build
- Published the container for `linux/amd64` and `linux/arm64`.
- Separated fast correctness checks from PostgreSQL-backed tests and added separate coverage reporting.
- Updated release tooling and used a source-only Docker build context.

### Docs
- Refreshed API documentation, feature-oriented README, deployment guidance and concise contributor restrictions.
- Configure the complete backing-service stack using the repository deployment documentation.

### Tests
- Expanded strict Music schema, generated-contract and catalog ownership coverage.
- Both released container platforms were built and public registry access was checked.
- The published image passed isolated PostgreSQL, authentication and Music search smoke checks.

### Release Baseline
- The current API, field contracts and fresh PostgreSQL baseline are marked version 1; this is not a rollback of the current schema or payloads.
- Pre-cutover databases are not silently converted. Keep existing data and backups separate from a fresh baseline installation.
- Future schema changes require explicit migrations.

### Docker
- `ghcr.io/collectarr/collectarr-core:1.0.0`
- Platforms: `linux/amd64`, `linux/arm64`.

**Full Changelog**: https://github.com/collectarr/collectarr-core/compare/v0.2.0...v1.0.0

## 0.2.0 - 2026-06-25

### Features
- Expanded typed metadata coverage across TV, movie, music, comics, books, boardgames, and game cutovers.
- Added provider-backed seed catalog data, TV release metadata endpoints, and supporting ingest/schema improvements.
- Continued admin and duplicate-review hardening around the newer kind-first model.

### Fixes
- Hardened metadata privacy, provider search/live paths, ingest mappings, and schema export snapshots.
- Removed legacy item models, shims, and routes that no longer belong in the v1 stack.
- Fixed ruff/import-order issues and tightened contract/test coverage.

### Refactors
- Split metadata builders, services, and typed reads/routes into smaller seams.
- Cleaned up legacy catalog/projection paths and release schema handling.
- Continued core cleanup around provider helpers and bundle/hash handling.

### CI & Build
- Refreshed contract artifacts, cleanup checks, and release configuration.

### Docs
- Refreshed schema exports, field registry docs, and cleanup notes.

### Tests
- Added coverage for TV routes, provider integrity, duplicate review, and metadata field schema contracts.

### Docker
- ghcr.io/collectarr/collectarr-core:v0.2.0
- ghcr.io/collectarr/collectarr-core:latest

**Full Changelog**: https://github.com/collectarr/collectarr-core/compare/v0.1.4...v0.2.0
