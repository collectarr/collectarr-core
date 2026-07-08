# Changelog

## [1.1.0](https://github.com/collectarr/collectarr-core/compare/v1.0.4...v1.1.0) (2026-07-08)

### Features
- Expanded typed metadata coverage across TV, movie, music, comics, books, boardgames, and game cutovers.
- Added provider-backed seed catalog data, TV release metadata endpoints, and supporting ingest/schema improvements.
- Continued admin and duplicate-review hardening around the newer kind-first model.

### Bug Fixes
- Hardened metadata privacy, provider search/live paths, ingest mappings, and schema export snapshots.
- Removed legacy item models, shims, and routes that no longer belong in the v1 stack.
- Fixed ruff/import-order issues and tightened contract/test coverage.

### Maintenance
- Refreshed docs, generated artifacts, and release/config cleanup around the metadata boundary.
