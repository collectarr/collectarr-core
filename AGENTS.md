# Collectarr Core Instructions

## Product boundary

Core owns source-neutral canonical catalog data and its read/write API. It must not own provider integrations, provider search or ingest runtime, or App-owned personal data such as owned copies, wishlist state, tracking progress, reading queues, loans, personal notes, local locations, purchase/sale data, or custom user-field values.

## Flattened catalog architecture

Each kind has one root aggregate per concrete collectible edition, version, issue variant, or release. The root combines fields that the legacy schema split between Work/Media and Release/Edition/Variant. Do not add a generic Work-to-Release graph.

Keep genuinely independent children in kind-owned tables, including Music media/tracks, TV and Anime seasons/episodes/media, Book printings, and kind-specific people, characters, credits, links, identifiers, and mappings.

Use separate typed root tables per kind. The planned roots are `music_items`, `tv_items`, `anime_items`, `movie_items`, `book_items`, `boardgame_items`, `game_items`, `manga_items`, and `comic_items`. A kind-local series may remain a grouping/reference, but it must not be a required editable parent in the catalog-item flow.

## Provider boundary

Provider search, credentials, rate limiting, source-ID mapping, snapshots, ingest, and provider administration belong outside Core and are removed for this implementation. Core APIs and contracts must remain source-neutral. Do not add provider envelopes, provider-support exports, or provider-specific IDs to the flattened catalog API.

## API and contracts

Prefer typed, kind-owned routes for flat roots and their real children. Export OpenAPI and the canonical field/identity contracts from their source schemas. Regenerate contracts after schema or route changes and keep the App's pinned contract in sync.

## Data migration

Preserve the pre-flattened App/Core baseline commits recorded in `docs/architecture/flattened-catalog-baseline.md`. Build deterministic one-way migrations from that baseline. Preserve concrete child IDs as root IDs when possible, copy shared metadata to every derived root, retain independent child identities, and record explicit old-to-new mappings for personal-state references. Detect orphans, collisions, and row-count mismatches; never silently discard or fan out personal records.

Do not run migrations against a live database, deploy, or reset production data. Provide fresh-database instructions separately from upgrade migrations.

## Local checks

Use the relevant local checks after implementation changes:

- `python -m scripts.export_contract_bundle`
- `python -m pytest`
- `python -m ruff check .`

Keep migration and contract tests that protect active behavior. If a check cannot be run, state why.
