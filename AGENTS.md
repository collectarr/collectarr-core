# Collectarr Core — Codex Instructions

## Product boundary
collectarr-core owns canonical catalog metadata, source-neutral catalog writes, typed metadata contracts, catalog administration, image/cache services, and contract exports for clients.

Provider search, API keys, rate limits, provider response mapping, provider IDs, raw snapshots, import jobs, and import history belong to `collectarr-app`. Core accepts already normalized, source-neutral catalog objects and must not expose provider search or provider-ingest routes.

collectarr-core must not model app-owned personal user data such as owned copies, wishlist state, tracking progress, reading queue, loans, personal notes, local location/storage, purchase/sale data, or custom user field values.

## Canonical schema direction
The active target is the coordinated all-kind Catalog Item v1 cutover documented in `docs/catalog-item-v1-cutover.md`.

Every kind has one canonical Catalog Item per concrete collectible edition/version/issue variant/release. It may contain typed child data such as tracks, episodes, credits, components, and included editions, but these children do not form another editable Work/Release chain. Core stores only shared canonical catalog data; App-owned copies, provider provenance, tracking, and personal fields remain outside Core.

Do not add new Work/Release graph semantics or compatibility aliases. Existing per-kind graph tables are transitional source structures and will be removed or replaced at the coordinated v1 reset. Do not deploy/reset a database until the all-kind contract and App switch are complete.

## API and contracts
Core's target client contract bundle is exported from contracts/ (the current
working bundle still contains the Music-only v1 slice until the all-kind
switch is complete):
- openapi.json
- catalog-item-v1.json
- metadata-field-schema.json
- active-kinds.json
- contract-manifest.json

When API schemas, metadata fields, or active kinds change:
1. update the source registry/schema
2. regenerate contracts
3. update tests
4. keep app compatibility in mind

Do not use docs/*.md as the machine contract source. The contracts/ JSON files are the machine-readable source for clients.

## Metadata field schema
Every exported metadata field should include:
- key
- kind or applicableKinds
- valueType
- scope
- writeTarget
- sourceEntityType
- sourceTable
- editable/searchable/filterable flags where applicable

Fields must distinguish canonical metadata from legacy projection fields.

## Typed routes
Prefer typed routes over generic metadata fallback routes.

Do not add new features to:
- /metadata/{kind}/{id}
- /metadata/items/...
unless the code is explicitly legacy compatibility.

Prefer typed Catalog Item routes with kind-qualified details. Do not expose
separate editable Work and Release roots for one collectible item.

## Refactor priorities
Prefer extracting from the large MetadataService into focused modules:
- typed reads
- search
- source-neutral canonical writes
- proposal/admin workflow
- facets
- images
- legacy projection
- per-kind handlers

Keep behavior-compatible tests when extracting.

## Local checks
Use the relevant local checks after changes:
- python -m scripts.export_contract_bundle
- python -m pytest
- python -m ruff check .

If a check cannot be run, state why.
