# Changelog

## [1.1.0](https://github.com/collectarr/collectarr-core/compare/v1.0.4...v1.1.0) (2026-07-08)

### Features
- Expanded typed metadata and provider-backed seed catalog support across the core domain.
- Added TV, movie, and music release metadata endpoints and kept the v1 kind cutovers moving forward.
- Improved admin and provider ingest coverage for the newer kind-first model.

### Bug Fixes
- Hardened metadata privacy boundaries, provider search/live paths, and schema export snapshots.
- Removed legacy item models, shims, and routes that no longer belong in the v1 stack.
- Fixed ruff/import-order issues and tightened the remaining contract and ingest tests.

### Maintenance
- Refreshed docs, generated artifacts, and cleanup work around the metadata boundary.
