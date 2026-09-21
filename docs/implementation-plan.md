# Collectarr Core — Implementation Plan

Core is the canonical metadata server. Provider adapters and importers run in
`collectarr-app`; Core accepts the versioned normalized submission contract and
persists typed kind-specific metadata.

## Completed

- Split Core from the original monorepo.
- Replaced the historical migration chain with the current schema v1 baseline.
- Removed generic legacy metadata tables from canonical writes.
- Added typed kind-specific catalog routes and contract exports.
- Added normalized provider envelopes with provenance, attribution, and image
  references.
- Added admin metadata corrections, duplicate review, audit logs, and image
  cache operations.
- Added PostgreSQL-backed search with optional Meilisearch indexing.

## Active Roadmap

### Metadata contract and canonical writes

- Expand typed field coverage for every active kind.
- Keep normalized submissions and OpenAPI contracts aligned.
- Add focused validation for provider provenance and relation writes.
- Keep new HTTP contracts under the `/api/v1` composition root; pre-v1 paths
  are explicit aliases only.
- Accept provider-independent canonical correction proposals against an exact
  `(kind, entity_type, entity_id, scope)` target with a base revision/hash.
  Core validates field scope and canonical write target, but does not resolve
  the entity or accept personal/Owned fields.

### Admin operations

- Expand duplicate review from confidence signals into an operator queue.
- Continue deployment hardening for internet-facing installations.

### Schema explorer

- Keep the interactive explorer separated into shared and kind-specific domains.
- Add progressive disclosure for dense relation-heavy sections.

### Scan-to-identify boundary

- Keep comics cover recognition and scan-to-identify local-first in the app.
- Core provides image storage and search primitives only.
