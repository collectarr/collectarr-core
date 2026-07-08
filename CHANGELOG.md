# Changelog

## [1.1.0](https://github.com/collectarr/collectarr-core/compare/v1.0.4...v1.1.0) (2026-07-08)

## What's Changed

### ✨ Features
- Expanded typed metadata coverage across TV, movie, music, comics, books, boardgames, and game cutovers.
- Added provider-backed seed catalog data, TV release metadata endpoints, and supporting ingest/schema improvements.
- Continued admin and duplicate-review hardening around the newer kind-first model.

### 🐛 Fixes
- Hardened metadata privacy, provider search/live paths, ingest mappings, and schema export snapshots.
- Removed legacy item models, shims, and routes that no longer belong in the v1 stack.
- Fixed ruff/import-order issues and tightened contract/test coverage.

### ♻️ Refactors
- Split metadata builders, services, and typed reads/routes into smaller seams.
- Cleaned up legacy catalog/projection paths and release schema handling.
- Continued core cleanup around provider helpers and bundle/hash handling.

### 🧰 CI & Build
- Refreshed contract artifacts, cleanup checks, and release configuration.

### 📚 Docs
- Refreshed schema exports, field registry docs, and cleanup notes.

### 🧪 Tests
- Added coverage for TV routes, provider integrity, duplicate review, and metadata field schema contracts.

### Docker
- ghcr.io/collectarr/collectarr-core:v1.1.0
- ghcr.io/collectarr/collectarr-core:latest

**Full Changelog**: https://github.com/collectarr/collectarr-core/compare/v1.0.4...v1.1.0
