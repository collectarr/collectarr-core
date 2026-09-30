# Collectarr Core Instructions

## Product boundary

Core owns source-neutral canonical catalog data and its read/write API. It must not own provider integrations, provider search or ingest runtime, or App-owned personal data such as owned copies, wishlist state, tracking progress, reading queues, loans, personal notes, local locations, purchase/sale data, or custom user-field values.

## Flattened catalog architecture

Each kind has one root aggregate per concrete collectible edition, version, issue variant, or release. The root keeps edition-level facts in one kind-owned aggregate. Do not add a generic Work-to-Release graph.

Keep genuinely independent children in kind-owned tables, including Music media/tracks, TV and Anime seasons/episodes/media, Book printings, and kind-specific people, characters, credits, links, identifiers, and mappings.

Use separate typed root tables per kind. The planned roots are `music_items`, `tv_items`, `anime_items`, `movie_items`, `book_items`, `boardgame_items`, `game_items`, `manga_items`, and `comic_items`. A kind-local series may remain a grouping/reference, but it must not be a required editable parent in the catalog-item flow.

## Provider boundary

The project has no provider search, credentials, rate limiting, source-ID mapping, snapshots, ingest, or provider administration subsystem. Do not reintroduce those features, compatibility identifiers, provider envelopes, provider-support exports, or provider-specific IDs. User Catalog Item proposals remain source-neutral and contain only the kind fields accepted by manual Add/Edit.

## API and contracts

Prefer typed, kind-owned routes for flat roots and their real children. Export OpenAPI and the canonical field/identity contracts from their source schemas. Regenerate contracts after schema or route changes and keep the App's pinned contract in sync.

## Database baseline

The supported database schema is created from the current typed SQLAlchemy models on a fresh, empty database. Runtime code does not transform existing schemas or archived payload formats. Existing databases and backups require an explicit external recovery decision; never reset or rewrite them as part of development work.

Keep local setup instructions explicit that the database must be new and empty. `create_all()` creates missing objects and does not reshape existing tables.

## Local checks

Use the relevant local checks after implementation changes:

- `python -m scripts.export_contract_bundle`
- `python -m pytest`
- `python -m ruff check .`

Keep schema and contract checks that protect active behavior. If a check cannot be run, state why.
